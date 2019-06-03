#!/usr/bin/python
import subprocess
import sys
import os
import datetime
import time
import requests
import boto3
import base64
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

from pprint import pprint

# Config
instance = "$instance_name"

worker_name="worker@{0}".format(instance)

az_to_subnet = $az_to_subnet

ec2_types = ["r3.8xlarge", "r4.8xlarge"]
worker_cpus = 32
price = "3.00"
ami = "ami-079f96ce4a4a7e1c7"
security_group = "$security_group"
user_data_file = {
    "r3.8xlarge": "/opt/scripts/provisioner/cloudinit.cfg",
    "r4.8xlarge": "/opt/scripts/provisioner/cloudinit_0.cfg"
}

ses_aws_access_key_id = "$ses_aws_access_key_id"
ses_aws_secret_access_key = "$ses_aws_secret_access_key"

bad_spot_zone_record_file = "/opt/scripts/provisioner/bad_spot_zone"

# Get number of cpus and nodes requested by jobs being in the idle state longer than 2 minutes (120 secs)
command = 'condor_q -format "%s\n" RequestCpus -constraint "JobStatus == 1 && QDate < $$(date +%s) - 120" | paste -sd+ | bc'
requested_cpus = subprocess.check_output(command, shell=True)
requested_cpus = requested_cpus.strip()

# exit if not requested cpu
if requested_cpus in ["", None]:
    sys.exit()

print "[{0}] ---Provisioner Start---".format(datetime.datetime.now())

# aws info to initiate clients
aws_meta_url = "http://169.254.169.254/latest/meta-data/"
availability_zone = requests.get((aws_meta_url + "placement/availability-zone")).content
aws_region = availability_zone[0:-1]

# helepers
# function for sending notification emails
def send_email(email_content):
    ses_client = boto3.client("ses", 
                        region_name=aws_region, 
                        aws_access_key_id=ses_aws_access_key_id,
                        aws_secret_access_key=ses_aws_secret_access_key)
    response = ses_client.send_email(
            Source="server@globusgenomics.org",
            Destination={"ToAddresses": ["xiao2@uchicago.edu"]},
            Message={
                "Subject": {
                    "Data": "manage dynamic pool info from {0}".format(instance),
                    "Charset": "UTF-8"
                },
                "Body": {
                    "Text": {
                        "Data": email_content,
                        "Charset": "UTF-8"
                    }
                }
            }
        )

def record_bad_spot_zone(request):
    instance_type_tmp = request["LaunchSpecification"]["InstanceType"]
    availability_zone_tmp = request["LaunchSpecification"]["Placement"]["AvailabilityZone"]
    # if the item exists, update its timestamp with the current time
    if os.path.isfile(bad_spot_zone_record_file):
        write_back = ""
        with open(bad_spot_zone_record_file) as f:
            lines = f.read().splitlines()
            lines = filter(None, lines)
            found = False
            for line in lines:
                info = line.split()
                if info[0] == instance_type_tmp and info[1] == availability_zone_tmp:
                    found = True
                    time_now = datetime.datetime.now()
                    info_to_write = "{0} {1} {2}\n".format(info[0], info[1], time_now.strftime("%m/%d/%Y/%H:%M:%S"))
                    write_back = write_back + info_to_write
                else:
                    write_back = write_back + line + "\n"
            if not found:
                send_email("spot status: \n{0}".format(request))
                time_now = datetime.datetime.now()
                info_to_write = "{0} {1} {2}\n".format(instance_type_tmp, availability_zone_tmp, time_now.strftime("%m/%d/%Y/%H:%M:%S"))
                write_back = write_back + info_to_write
        with open(bad_spot_zone_record_file, "w") as f:
            f.write(write_back)
    else:
        send_email("spot status: \n{0}".format(request))
        time_now = datetime.datetime.now()
        info_to_write = "{0} {1} {2}\n".format(instance_type_tmp, availability_zone_tmp, time_now.strftime("%m/%d/%Y/%H:%M:%S"))
        with open(bad_spot_zone_record_file, "w") as f:
            f.write(info_to_write) 

# read and filter bad_spot_zone records
def get_and_filter_bad_spot_zone_list():
    # return a list of pairs
    # also remove the zones that are listed bad for more than 2 hours
    return_list = []
    if os.path.isfile(bad_spot_zone_record_file):
        write_back = ""
        with open(bad_spot_zone_record_file) as f:
            lines = f.read().splitlines()
            lines = filter(None, lines)
            for line in lines:
                info = line.split()
                info_time = datetime.datetime.strptime(info[2], "%m/%d/%Y/%H:%M:%S")
                time_now = datetime.datetime.now()
                if (time_now - info_time).total_seconds() < 7200:
                    write_back = write_back + line + "\n"
                    return_list.append([info[0], info[1]])
        with open(bad_spot_zone_record_file, "w") as f:
            f.write(write_back)
    return return_list

# requested cpus
requested_cpus = int(requested_cpus)
print "Requested CPUs: {0}".format(requested_cpus)
# requested node num
nodes = requested_cpus/worker_cpus
if requested_cpus%worker_cpus > 0:
    nodes = nodes + 1
print "Requested nodes: {0}".format(nodes)

# Unclaimed nodes are a sum of three types of requests:
# 1) open spot requests,
# 2) active spot requests that correspond to pending instances,
# 3) active spot requests that correspond to running instances not claimed yet as condor nodes.
client = boto3.client('ec2', region_name=aws_region)

# open requests
response = client.describe_spot_instance_requests(
        Filters=[
            {
                "Name": "tag:Name",
                "Values": [
                    worker_name,
                ]
            },
            {
                "Name": "state",
                "Values": [
                    "open",
                ]
            },
        ]
    )


# analyze the open requests
open_spot_requests = response["SpotInstanceRequests"]
healthy_open_spot_requests_num = len(open_spot_requests)
MONITORED_SPOT_STATUS_CODE = ["capacity-not-available",
                              "capacity-oversubscribed",
                              "price-too-low",
                              "not-scheduled-yet",
                              "launch-group-constraint",
                              "az-group-constraint",
                              "placement-group-constraint",
                              "constraint-not-fulfillable"]
for request in open_spot_requests:
    spot_status_code = request["Status"]["Code"]
    if spot_status_code in MONITORED_SPOT_STATUS_CODE:
        healthy_open_spot_requests_num = healthy_open_spot_requests_num - 1
        record_bad_spot_zone(request)
        try:
            client.cancel_spot_instance_requests(SpotInstanceRequestIds=[request["SpotInstanceRequestId"]])
        except Exception as e:
            send_email("failed to cancel spot request: message: {0} \n {1}".format(e, request))


unclaimed_nodes_num = healthy_open_spot_requests_num

if unclaimed_nodes_num >= nodes:
    sys.exit()

# active requests
response = client.describe_spot_instance_requests(
        Filters=[
            {
                "Name": "tag:Name",
                "Values": [
                    worker_name,
                ]
            },
            {
                "Name": "state",
                "Values": [
                    "active",
                ]
            },
        ]
    )
active_spot_requests = response["SpotInstanceRequests"]

if active_spot_requests != []:
    active_spot_instances_ids = []
    for request in active_spot_requests:
        active_spot_instances_ids.append(request["InstanceId"])

    # tag the running instances
    client.create_tags(
        Resources=active_spot_instances_ids,
        Tags=[
            {
                "Key": "Name",
                "Value": worker_name
            },
            {
                "Key": "owner",
                "Value": "globus"
            }
        ]
    )

    # pending instances
    response = client.describe_instances(
            Filters=[
                {
                    "Name": "instance-state-name",
                    "Values": [
                        "pending",
                    ]
                },
            ],
            InstanceIds=active_spot_instances_ids
        )
    pending_instances = response["Reservations"]
    pending_instances_num = len(pending_instances)
    print "Pending instances number: {0}".format(pending_instances_num)
    unclaimed_nodes_num = unclaimed_nodes_num + pending_instances_num
    if unclaimed_nodes_num >= nodes:
        sys.exit()

    # running instances
    response = client.describe_instances(
            Filters=[
                {
                    "Name": "instance-state-name",
                    "Values": [
                        "running",
                    ]
                },
            ],
            InstanceIds=active_spot_instances_ids
        )
    running_instances = response["Reservations"]
    # check is the running is instance is claimed by condor
    for running_instance in running_instances:
        running_instance_private_dns_name = running_instance["Instances"][0]["PrivateDnsName"]
        try:
            command = "condor_status -claimed -direct {0} 2>/dev/null".format(running_instance_private_dns_name)
            claimed = subprocess.check_output(command, shell=True)
            claimed = claimed.strip()
        except:
            claimed = None
        if claimed in ["", None]:
            instance_id = running_instance["Instances"][0]["InstanceId"]
            launch_time = running_instance["Instances"][0]["LaunchTime"].replace(tzinfo=None)
            print "Unclaimed running instance: {0}, {1}, launched {2}".format(instance_id, running_instance_private_dns_name, launch_time)
            if (datetime.datetime.now() - launch_time).total_seconds() < 3600:
                unclaimed_nodes_num = unclaimed_nodes_num + 1
            else:
                print "Terminating the unclaimed running instance: {0}, {1}, launched {2}".format(instance_id, running_instance_private_dns_name, launch_time)
                email_content = "Terminating the unclaimed running instance: {0}, {1}, launched {2}".format(instance_id, running_instance_private_dns_name, launch_time)
                send_email(email_content)
                try:
                    client.terminate_instances(InstanceIds=[instance_id])
                except Exception as e: print e

# ready to request spot instance
nodes = nodes - unclaimed_nodes_num

# limit the number of nodes to request at same time
if nodes > 5:
    print "Nodes requesting: {0}, changing it to 5".format(nodes)
    nodes = 5

# Request spot instances in the cheapest availability zone
if nodes > 0:
    # get the available zones
    az_list = az_to_subnet.keys()
    available_az_type_pairs = []
    bad_spot_zone_list = get_and_filter_bad_spot_zone_list()
    for ec2_type in ec2_types:
        for az in az_list:
            pair_tmp = [ec2_type, az]
            if pair_tmp not in bad_spot_zone_list:
                available_az_type_pairs.append(pair_tmp)

    # Find the cheapest availability zone among those we have mapped to subnets
    current_time = datetime.datetime.now()
    min_price=1000.0
    best_pair = available_az_type_pairs[0]

    for pair in available_az_type_pairs:
        response = client.describe_spot_price_history(
                AvailabilityZone=pair[1],
                InstanceTypes=[pair[0]],
                MaxResults=1,
                ProductDescriptions=["Linux/UNIX"],
                StartTime=current_time
            )
        if response["SpotPriceHistory"] != []:
            new_price = float(response["SpotPriceHistory"][0]["SpotPrice"])
            print "current price, {0} {1}: {2}".format(pair[0], pair[1], new_price)
            if new_price < min_price:
                min_price = new_price
                best_pair = pair

    print "Best zone: {0} {1}".format(best_pair[0], best_pair[1])

    print "Actual nodes requesting: {0}".format(nodes)
    with open(user_data_file[best_pair[0]], "r") as r:
        user_data = r.read()
    if best_pair[0] == "r3.8xlarge":
        response = client.request_spot_instances(
                LaunchSpecification={
                    "ImageId": ami,
                    "KeyName": "galaxy",
                    "InstanceType": best_pair[0],
                    "BlockDeviceMappings": [
                        {
                            "DeviceName": "/dev/sda1",
                            "Ebs": {
                                "VolumeSize": 10
                            }
                        },
                        {
                            "DeviceName": "/dev/sdb",
                            "VirtualName": "ephemeral0"
                        },
                        {
                            "DeviceName": "/dev/sdc",
                            "VirtualName": "ephemeral1"
                        },
                        {
                            "DeviceName": "/dev/sdd",
                            "VirtualName": "ephemeral2"
                        },
                        {
                            "DeviceName": "/dev/sde",
                            "VirtualName": "ephemeral3"
                        }
                    ],
                    "SubnetId": az_to_subnet[best_pair[1]],
                    "SecurityGroupIds": [security_group],
                    "UserData": base64.b64encode(user_data)
                },
                SpotPrice=price,
                InstanceCount=nodes
            )
    elif best_pair[0] == "r4.8xlarge":
        response = client.request_spot_instances(
                LaunchSpecification={
                    "ImageId": ami,
                    "KeyName": "galaxy",
                    "InstanceType": best_pair[0],
                    "BlockDeviceMappings": [
                        {
                            "DeviceName": "/dev/sda1",
                            "Ebs": {
                                "VolumeSize": 10
                            }
                        },
                        {
                            "DeviceName": "/dev/sdb",
                            "VirtualName": "ephemeral0",
                            "Ebs": {
                                "DeleteOnTermination": True,
                                "VolumeSize": 300,
                                "VolumeType": "gp2",
                                "Encrypted": False,
                            },
                        }
                    ],
                    "SubnetId": az_to_subnet[best_pair[1]],
                    "SecurityGroupIds": [security_group],
                    "UserData": base64.b64encode(user_data)
                },
                SpotPrice=price,
                InstanceCount=nodes
            )
    else:
        raise ValueError("instance type not supported: {0}".format(best_pair[0]))
    
    time.sleep(10)
    spot_requests = response["SpotInstanceRequests"]
    spot_requests_ids = []
    for sr in spot_requests:
        spot_requests_ids.append(sr["SpotInstanceRequestId"])
    print "Spot requests: {0}".format(spot_requests_ids)
    # tag the spot requests
    client.create_tags(
        Resources=spot_requests_ids,
        Tags=[
            {
                "Key": "Name",
                "Value": worker_name
            },
            {
                "Key": "owner",
                "Value": "globusgenomics"
            }
        ]
    )

print "[{0}] ---Provisioner End---".format(datetime.datetime.now())
