import sys
import subprocess
import os
from pprint import pprint
import requests
import pwd
import grp
import json
import copy
from string import Template
import ConfigParser
import difflib
import re
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
creds_config = ConfigParser.ConfigParser()
creds_config.read("secret/creds")

if action == "launch":
    # prepare configs for chef-solo
    # solo.rb
    node_name = instance_config["name"]
    node_name_short = node_name.split(".")[0]
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
    to_write["run_list"] = run_list_step_1
    to_write["genomics_sec_dir"] = os.path.join(current_path, "secret") # where the secret is kept
    to_write["nfs_export"] = instance_config["nfs_export_dirs"]
    to_write["aws"] = {"worker_subnets": instance_config["aws"]["worker_subnets"],
                        "worker_security_group": instance_config["aws"]["worker_security_group"]
                      }
    to_write["provisioner"] = {"use_on_demand_instance": json.dumps(instance_config["provisioner"]["use_on_demand_instance"]),
                               "worker": {
                                    "worker_type": instance_config["provisioner"]["worker"]["worker_type"],
                                    "worker_bid_price": instance_config["provisioner"]["worker"]["worker_bid_price"],
                                    "worker_num_cpus": instance_config["provisioner"]["worker"]["worker_num_cpus"],
                                    "worker_is_hvm": json.dumps(instance_config["provisioner"]["worker"]["worker_is_hvm"]),
                                    "merged_ephemerals": json.dumps(instance_config["provisioner"]["worker"]["merged_ephemerals"])
                                    }
                              }
    to_write["database"] = {"use_rds_postgresql_server": json.dumps(instance_config["database"]["use_rds_postgresql_server"])}

    to_write_copy = copy.deepcopy(to_write)
    to_write_copy["run_list"] = run_list_step_2
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

    # configure galaxy.ini
    if instance_config["database"]["use_rds_postgresql_server"]:
        database_connection = "postgresql://{0}:{1}@rds.ops.globusgenomics.org:5432/galaxy_{2}".format(creds_config.get("rds", "user"), creds_config.get("rds", "password"), node_name_short)
    else:
        database_connection = "postgres:///galaxy_{0}?user=galaxy&password=galaxy&host=/var/run/postgresql".foramt(node_name_short)
    if "galaxy" in instance_config and "tool_data_path" in instance_config["galaxy"]:
        tool_data_path = instance_config["galaxy"]["tool_data_path"]
    else:
        tool_data_path = "tool-data"
    if "galaxy" in instance_config and "len_file_path" in instance_config["galaxy"]:
        len_file_path = instance_config["galaxy"]["len_file_path"]
    else:
        len_file_path = "/mnt/galaxyIndices/galaxy/chrom"
    if "galaxy" in instance_config and "admin_users" in instance_config["galaxy"]:
        admin_users = main_config["galaxy"]["admin_users"] + "," + instance_config["galaxy"]["admin_users"]
    else:
        admin_users = main_config["galaxy"]["admin_users"]
    config_info = {
        "node_name_short": node_name_short,
        "globus_group_id": instance_config["globus"]["globus_group_id"],
        "database_connection": database_connection,
        "tool_data_path": tool_data_path,
        "len_file_path": len_file_path,
        "admin_users": admin_users,
        "id_secret": creds_config.get("galaxy", "id_secret")
    }
    template = open( 'files/galaxy.ini.template' )
    src = Template( template.read() )
    updated_content = src.safe_substitute(config_info)
    with open("/opt/galaxy/config/galaxy.ini", "r") as f:
        old_content = f.read()
    if old_content != updated_content:
        for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile="galaxy.ini", tofile="updated galaxy.ini"):
            print text
        with open("/opt/galaxy/config/galaxy.ini", "w") as f:
            f.write(updated_content)

    # configure job_conf.xml
    updated_content = ""
    worker_num_cpus = instance_config["provisioner"]["worker"]["worker_num_cpus"]
    with open("/opt/galaxy/config/job_conf.xml", "r") as f:
        old_content = f.read()
    for line in old_content.split("\n"):
        if ('destination="condor_remote_' in line) and \
           (int(re.search('destination="condor_remote_(.*)"', line).group(1)) > int(worker_num_cpus)):
            updated_line = worker_num_cpus.join(line.rsplit(re.search('destination="condor_remote_(.*)"', line).group(1), 1))
            updated_content = updated_content + updated_line + "\n"
        else:
            updated_content = updated_content + line + "\n"
    if updated_content.endswith("\n"):
        updated_content = updated_content[:-1]
    if old_content != updated_content:
        for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile="job_conf.xml", tofile="updated job_conf.xml"):
            print text
        with open("/opt/galaxy/config/job_conf.xml", "w") as f:
            f.write(updated_content)

    # configure tool_conf.xml
    updated_content = filter_tool_conf(node_name_short, "/opt/galaxy/config/tool_conf.xml")
    with open("/opt/galaxy/config/tool_conf.xml", "r") as f:
        old_content = f.read()
    if old_content != updated_content:
        for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile="tool_conf.xml", tofile="updated tool_conf.xml"):
            print text
        with open("/opt/galaxy/config/tool_conf.xml", "w") as f:
            f.write(updated_content)


    # run chef-solo_step_2
    command = "chef-solo -c solo.rb -j solo_config_step_2.json"
    subprocess.call(command, shell=True)
