import sys
import subprocess
import os
from pprint import pprint
import requests
import pwd
import grp
import json
import copy
from helper import *

from optparse import OptionParser
args=None
parser = OptionParser()

parser.add_option("--action", dest="action", help="launch or update")
parser.add_option("--instance", dest="instance", help="instance")

options, args = parser.parse_args(args)

action = options.action
if action not in ["launch", "update"]:
    sys.exit("invalid action")

instance = options.instance

with open("config/main.config") as f:
    main_config = eval(f.read())

pprint(main_config)

with open("config/releases.config") as f:
    releases_config = eval(f.read())

pprint(releases_config)

instance_config_path = "config/instance/{0}".format(instance)
with open(instance_config_path) as f:
    instance_config = eval(f.read())

pprint(instance_config)

current_path = os.getcwd() #os.path.dirname(os.path.realpath(__file__))

aws_meta_url = "http://169.254.169.254/latest/meta-data/"

if action == "launch":
    # prepare configs for chef-solo
    # solo.rb
    node_name = instance_config["name"]
    to_write = """
node_name "%s"

current_dir = File.dirname(__FILE__)

file_cache_path "#{current_dir}/genomics-chef-solo/cache"
cookbook_path "#{current_dir}/genomics-chef-solo/cookbooks"
data_bag_path "#{current_dir}/genomics-chef-solo/data_bags"
role_path "#{current_dir}/genomics-chef-solo/roles"
solo true
    """ % (node_name)

    with open("solo.rb", "w") as f:
        f.write(to_write)

    # solo_config.json
    to_write = {}
    tmp1 = main_config["instance_setup"]["chef"]["run_list_step_1"].split(",")
    run_list_step_1 = []
    for item in tmp1:
        run_list_step_1.append(str(item.strip()))
    tmp2 = main_config["instance_setup"]["chef"]["run_list_step_2"].split(",")
    run_list_step_2 = []
    for item in tmp2:
        run_list_step_2.append(str(item.strip()))
    run_list = []
    run_list.append(instance_config["worker_type"]) # worker type config
    to_write["run_list"] = run_list + run_list_step_1
    to_write["genomics_sec_dir"] = os.path.join(current_path, "secret") # where the secret is kept
    to_write["nfs_export"] = instance_config["nfs_export_dirs"]
    to_write["aws"] = {"worker_subnets": instance_config["aws"]["worker_subnets"],
                        "worker_security_group": instance_config["aws"]["worker_security_group"]}
    to_write["provisioner"] = {"use_on_demand_instance": json.dumps(instance_config["provisioner"]["use_on_demand_instance"])}
    to_write["database"] = {"use_rds_postgresql_server": json.dumps(instance_config["database"]["use_rds_postgresql_server"])}

    to_write_copy = copy.deepcopy(to_write)
    to_write_copy["run_list"] = run_list + run_list_step_2
    to_write = str(to_write).replace("\'", "\"")
    to_write_copy = str(to_write_copy).replace("\'", "\"")
    with open("solo_config_step_1.json", "w") as f:
        f.write(to_write)
    with open("solo_config_step_2.json", "w") as f:
        f.write(to_write_copy)

    # run chef-solo_step_1
    command = "chef-solo -c solo.rb -j solo_config_step_1.json"
    subprocess.call(command, shell=True)

    """
    # create and attach the required volumes
    availability_zone = requests.get((aws_meta_url + "placement/availability-zone")).content
    aws_region = availability_zone[0:-1]
    instance_id = requests.get((aws_meta_url + "instance-id")).content
    #volumes_info = dict(main_config["volumes"].items() + instance_config["volumes"].items())
    volumes_info = instance_config["volumes"]

    for volume_name, volume_info in volumes_info.iteritems():
        
        if "snapshot_id" in volume_info:
            if volume_info["snapshot_id"] == "current_release":
                snapshot_id = releases_config[main_config["current_release"]]["snapshots"][volume_name]
            else:
                snapshot_id = volume_info["snapshot_id"]
            file_system = None
        else:
            snapshot_id = None
            file_system = volume_info["file_system"]

        encrypted = volume_info["encrypted"]
        if encrypted == True:
            kms_key_id = instance_config["aws"]["kms_key_id"]
        else:
            kms_key_id = None

        size = volume_info["size"]

        volume_type = volume_info["volume_type"]

        tag = "{0} ({1})".format(instance_config["name"], volume_name)

        device = volume_info["mount_device"]
        mount_point = volume_info["mount_point"]

        if "mount_point_user" in volume_info:
            mount_point_user = volume_info["mount_point_user"]
        else:
            mount_point_user = None

        create_ec2_volume(region=aws_region,
                  AvailabilityZone=availability_zone, 
                  Encrypted=encrypted,
                  KmsKeyId=kms_key_id,
                  Size=size,
                  SnapshotId=snapshot_id,
                  VolumeType=volume_type,
                  Tag=tag,
                  InstanceId=instance_id,
                  Device=device,
                  file_system=file_system,
                  mount_point=mount_point,
                  mount_point_user=mount_point_user)

    # nfs setup
    nfs_export_dirs = instance_config["nfs_export_dirs"]
    for item in nfs_export_dirs:
        to_insert = "{0} *(rw,sync,root_squash,no_subtree_check)\n".format(item)
        with open('/etc/exports', 'r+') as f:
            for line in f:
                if line.startswith(to_insert):
                    print 'Found line in /etc/exports.'
                    break
            else:
                f.write(to_insert)

    #create /opt/galaxy
    if not os.path.exists("/opt/galaxy"):
        os.makedirs("/opt/galaxy")
        uid = pwd.getpwnam("galaxy").pw_uid
        gid = grp.getgrnam("galaxy").gr_gid
        os.chown("/opt/galaxy", uid, gid)

    command = "exportfs -a"
    subprocess.call(command, shell=True)
    command = "service nfs-kernel-server start"
    subprocess.call(command, shell=True)"""

    # download and configure Galaxy
    genomics_galaxy_version = instance_config["genomics_galaxy_version"]
    if genomics_galaxy_version == "current_release":
        genomics_galaxy_version = releases_config[main_config["current_release"]]["galaxy_repo_commit_hash"]
    command = "git clone https://github.com/globusgenomics/genomics-galaxy-dev.git /opt/galaxy; cd /opt/galaxy; git checkout {0}".format(genomics_galaxy_version)
    #subprocess.call(command, shell=True, preexec_fn=demote(pwd.getpwnam("galaxy").pw_uid, grp.getgrnam("galaxy").gr_gid))



    # run chef-solo_step_2
    command = "chef-solo -c solo.rb -j solo_config_step_2.json"
    #subprocess.call(command, shell=True)
