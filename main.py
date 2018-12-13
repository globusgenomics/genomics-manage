import sys
import subprocess
import os
from pprint import pprint
import requests
import pwd
import grp
import ConfigParser
from helper import *

from optparse import OptionParser
args=None
parser = OptionParser()

"""
run as root
Example commands:
python main.py --action launch --instance test1.globusgenomics.org
python main.py --action update --instance test1.globusgenomics.org --update-type chef-solo_step_2
python main.py --action update --instance test1.globusgenomics.org --update-type chef-solo_step_1
python main.py --action update --instance test1.globusgenomics.org --update-type galaxy
python main.py --action update --instance test1.globusgenomics.org --update-type galaxy --backup-galaxy
python main.py --action update --instance test1.globusgenomics.org --update-type galaxy-reports
python main.py --action test-function --instance test1.globusgenomics.org
"""

parser.add_option("--action", dest="action", help="launch, config, update")
parser.add_option("--instance", dest="instance", help="instance")
parser.add_option("--update-type", dest="update_type", help="update type")
parser.add_option("--backup-galaxy", dest="backup_galaxy", help="backup old galaxy when update galaxy", action="store_true", default=False)

options, args = parser.parse_args(args)

print "#### Working on {0}".format(options.instance)

# check the inputs
if options.action not in ["launch", "update", "test-function"]:
    sys.exit("invalid action")
assert options.instance != None

with open("config/main.config") as f:
    main_config = eval(f.read())

pprint(main_config)

with open("config/releases.config") as f:
    releases_config = eval(f.read())

pprint(releases_config)

instance_config_path = "config/instance/{0}".format(options.instance)
with open(instance_config_path) as f:
    instance_config = eval(f.read())

pprint(instance_config)

current_path = os.getcwd() #os.path.dirname(os.path.realpath(__file__))
aws_meta_url = "http://169.254.169.254/latest/meta-data/"
creds_config = ConfigParser.ConfigParser()
creds_config.read("secret/creds")


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

# solo_config.json base configs
solo_config_base = {}
solo_config_base["genomics_sec_dir"] = os.path.join(current_path, "secret") # where the secret is kept
solo_config_base["nfs_export"] = instance_config["nfs_export_dirs"]
solo_config_base["aws"] = {"worker_subnets": instance_config["aws"]["worker_subnets"],
                    "worker_security_group": instance_config["aws"]["worker_security_group"]
                  }
solo_config_base["provisioner"] = instance_config["provisioner"]
solo_config_base["database"] = instance_config["database"]


# launch action
if options.action == "launch":
    # run chef-solo_step_1
    run_list = main_config["instance_setup"]["chef"]["run_list_step_1"].split(",")
    execute_chef_run_list(solo_config_base=solo_config_base, run_list=run_list)

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
    subprocess.call(command, shell=True)

    # download and configure Galaxy
    download_galaxy(main_config=main_config, instance_config=instance_config, releases_config=releases_config)
    # configure galaxy.ini
    configure_galaxy_ini(main_config=main_config, instance_config=instance_config, creds_config=creds_config, node_name_short=node_name_short)
    # configure job_conf.xml
    configure_galaxy_job_conf(instance_config=instance_config)
    # configure tool_conf.xml
    configure_galaxy_tool_conf(node_name_short=node_name_short)
    # update gg version num
    update_gg_version_in_welcome_page(main_config=main_config, instance_config=instance_config)

    # run chef-solo_step_2
    run_list = main_config["instance_setup"]["chef"]["run_list_step_2"].split(",")
    execute_chef_run_list(solo_config_base=solo_config_base, run_list=run_list)

# update action
if options.action == "update":
    if options.update_type == None:
        sys.exit("Please specify --update-type")
    elif options.update_type == "chef-solo_step_2":
        # run chef-solo_step_2
        run_list = main_config["instance_setup"]["chef"]["run_list_step_2"].split(",")
        execute_chef_run_list(solo_config_base=solo_config_base, run_list=run_list)
    elif options.update_type == "chef-solo_step_1":
        # run chef-solo_step_1
        run_list = main_config["instance_setup"]["chef"]["run_list_step_1"].split(",")
        execute_chef_run_list(solo_config_base=solo_config_base, run_list=run_list)
    elif options.update_type == "galaxy":
        command = "supervisorctl stop galaxy:"
        subprocess.call(command, shell=True)
        if options.backup_galaxy:
            print "backup galaxy..."
            mv_and_backup_galaxy()
        else:
            print "remove /opt/galaxy..."
            command = "rm -r /opt/galaxy"
            subprocess.call(command, shell=True)
        if not os.path.exists("/opt/galaxy"):
            os.makedirs("/opt/galaxy")
            uid = pwd.getpwnam("galaxy").pw_uid
            gid = grp.getgrnam("galaxy").gr_gid
            os.chown("/opt/galaxy", uid, gid)
        # download and configure Galaxy
        download_galaxy(main_config=main_config, instance_config=instance_config, releases_config=releases_config)
        # configure galaxy.ini
        configure_galaxy_ini(main_config=main_config, instance_config=instance_config, creds_config=creds_config, node_name_short=node_name_short)
        # configure job_conf.xml
        configure_galaxy_job_conf(instance_config=instance_config)
        # configure tool_conf.xml
        configure_galaxy_tool_conf(node_name_short=node_name_short)
        # update gg version num
        update_gg_version_in_welcome_page(main_config=main_config, instance_config=instance_config)
        # run _galaxy recipe
        execute_chef_run_list(solo_config_base=solo_config_base, run_list=["recipe[genomics::_galaxy]"])
        command = "supervisorctl start galaxy:"
        subprocess.call(command, shell=True)
    elif options.update_type =="galaxy-reports":
        # start galaxy-reports
        execute_chef_run_list(solo_config_base=solo_config_base, run_list=["recipe[genomics::_galaxy_reports]"])
    else:
        sys.exit("update type not supported.")

# test-function action
if options.action == "test-function":
    update_gg_version_in_welcome_page(main_config=main_config, instance_config=instance_config)
