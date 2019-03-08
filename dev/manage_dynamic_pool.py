#!/usr/bin/python
import subprocess
import sys
import datetime
import requests
import boto3
import base64
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

from pprint import pprint

instance = "dev"

worker_name="worker@{0}".format(instance)

az_to_subnet = {
    "us-east-1a": "subnet-824316af",
    "us-east-1b": "subnet-68221821",
    "us-east-1c": "subnet-79eaaa22",
    "us-east-1e": "subnet-f68d04ca"
}

ec2_type = "r3.8xlarge"
worker_cpus = 32
price = "3.00"

ami = "ami-d05e75b8"
security_group = "sg-193ba365"
user_data_file = "/opt/scripts/cloudinit.cfg"


# Get number of cpus and nodes requested by jobs being in the idle state longer than 2 minutes (120 secs)
command = 'condor_q -format "%s\n" RequestCpus -constraint "JobStatus == 1 && QDate < $(date +%s) - 120" | paste -sd+ | bc'
requested_cpus = subprocess.check_output(command, shell=True)
requested_cpus = requested_cpus.strip()

if requested_cpus in ["", None]:
    sys.exit()

print "[{0}] ---Provisioner Start---".format(datetime.datetime.now())
requested_cpus = int(requested_cpus)
print "Requested CPUs: {0}".format(requested_cpus)

nodes = requested_cpus/worker_cpus

if requested_cpus%worker_cpus > 0:
    nodes = nodes + 1

print "Requested nodes: {0}".format(nodes)

# Unclaimed nodes are a sum of three types of requests:
# 1) open spot requests,
# 2) active spot requests that correspond to pending instances,
# 3) active spot requests that correspond to running instances not claimed yet as condor nodes.
aws_meta_url = "http://169.254.169.254/latest/meta-data/"
availability_zone = requests.get((aws_meta_url + "placement/availability-zone")).content
aws_region = availability_zone[0:-1]
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

unclaimed_nodes_num = len(response["SpotInstanceRequests"])

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
    for running_instance in running_instances:
        running_instance_private_dns_name = running_instance["Instances"][0]["PrivateDnsName"]
        try:
            command = "condor_status -claimed -direct {0} 2>/dev/null".format(running_instance_private_dns_name)
            claimed = subprocess.check_output(command, shell=True)
            claimed = requested_cpus.strip()
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
                try:
                    client.terminate_instances(InstanceIds=[instance_id])
                except Exception as e: print e

# ready to request spot instance
nodes = nodes - unclaimed_nodes_num

# limit the number of nodes to request at same time
if nodes > 5:
    nodes = 5

# Find the cheapest availability zone among those we have mapped to subnets
current_time = datetime.datetime.now()
min_price=1000.0
zone = az_to_subnet.keys()[0]
for z in az_to_subnet:
    response = client.describe_spot_price_history(
            AvailabilityZone=z,
            InstanceTypes=[ec2_type],
            MaxResults=1,
            ProductDescriptions=["Linux/UNIX"],
            StartTime=current_time
        )
    if response["SpotPriceHistory"] != []:
        new_price = float(response["SpotPriceHistory"][0]["SpotPrice"])
        if new_price < min_price:
            min_price = new_price
            zone = z

# Request spot instances in the cheapest availability zone
if nodes > 0:
    with open(user_data_file, "r") as r:
        user_data = r.read()

    response = client.request_spot_instances(
            LaunchSpecification={
                "ImageId": ami,
                "KeyName": "galaxy",
                "InstanceType": ec2_type,
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
                "SubnetId": az_to_subnet[zone],
                "SecurityGroupIds": [security_group],
                "UserData": base64.b64encode(user_data)
            },
            SpotPrice=price,
            InstanceCount=nodes
        )

    spot_requests = response["SpotInstanceRequests"]
    spot_requests_ids = []
    for sr in spot_requests:
        spot_requests_ids.append(sr["SpotInstanceRequestId"])
    print "Spot requests: {0}".format(spot_requests_ids)
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

