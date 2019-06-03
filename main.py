import sys
import subprocess
import os
from pprint import pprint
import requests
import pwd
import grp
import ConfigParser
from helper import *
from provisioner import *

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
python main.py --action update --instance test1.globusgenomics.org --update-type volume --volume-name galaxyTools
python main.py --action update --instance test1.globusgenomics.org --update-type release_update
python main.py --action update --instance test1.globusgenomics.org --update-type release_update --backup-galaxy
python main.py --action test-function --instance test1.globusgenomics.org
"""

parser.add_option("--action", dest="action", help="launch, config, update")
parser.add_option("--instance", dest="instance", help="instance")
parser.add_option("--update-type", dest="update_type", help="update type")
parser.add_option("--backup-galaxy", dest="backup_galaxy", help="backup old galaxy when update galaxy", action="store_true", default=False)
parser.add_option("--volume-name", dest="volume_name", help="volume name")

options, args = parser.parse_args(args)

print "#### Working on {0}".format(options.instance)

# check the inputs
if options.action not in ["launch", "update", "test-function"]:
    sys.exit("invalid action")
assert options.instance != None

# main config
with open("config/main.config") as f:
    main_config = eval(f.read())
pprint(main_config)

# release condig
with open("config/releases.config") as f:
    releases_config = eval(f.read())
pprint(releases_config)

# instance config
instance_config_path = "config/instance/{0}".format(options.instance)
with open(instance_config_path) as f:
    instance_config = eval(f.read())
pprint(instance_config)

# creds config
creds_config = ConfigParser.ConfigParser()
creds_config.read("secret/creds")

# instance aws info
aws_meta_url = "http://169.254.169.254/latest/meta-data/"
availability_zone = requests.get((aws_meta_url + "placement/availability-zone")).content
aws_region = availability_zone[0:-1]
instance_id = requests.get((aws_meta_url + "instance-id")).content
private_ip = requests.get((aws_meta_url + "local-ipv4")).content
instance_aws_info = {
    "availability_zone": availability_zone,
    "aws_region": aws_region,
    "instance_id": instance_id,
    "private_ip": private_ip
}

current_path = os.getcwd() #os.path.dirname(os.path.realpath(__file__))

# prepare configs for chef-solo
# solo.rb
node_name = instance_config["name"]
node_name_short = node_name.split(".")[0]
domain_name = node_name[node_name.find(".") + 1 :]

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
    #volumes_info = dict(main_config["volumes"].items() + instance_config["volumes"].items())
    volumes_info = instance_config["volumes"]

    for volume_name, volume_info in volumes_info.iteritems():
        create_volume(volume_name=volume_name, 
                      volume_info=volume_info,
                      releases_config=releases_config,
                      main_config=main_config,
                      instance_config=instance_config,
                      instance_aws_info=instance_aws_info )

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
    # update tool_data_table_conf.xml if necessary
    #update_tool_data_table_conf(instance_config=instance_config)
    # update gg version num
    update_gg_version_in_welcome_page(main_config=main_config, instance_config=instance_config, releases_config=releases_config)
    # extra steps
    extra_steps(creds_config=creds_config, node_name_short=node_name_short)

    # run chef-solo_step_2
    run_list = main_config["instance_setup"]["chef"]["run_list_step_2"].split(",")
    execute_chef_run_list(solo_config_base=solo_config_base, run_list=run_list)

    # deploy provisioner
    deploy_provisioner(instance_aws_info=instance_aws_info, node_name=node_name, node_name_short=node_name_short, domain_name=domain_name, instance_config=instance_config, creds_config=creds_config)

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
        reinstall_galaxy(main_config=main_config,
                         instance_config=instance_config,
                         releases_config=releases_config,
                         backup_galaxy=options.backup_galaxy,
                         creds_config=creds_config,
                         node_name_short=node_name_short,
                         solo_config_base=solo_config_base)
    elif options.update_type =="galaxy-reports":
        # start galaxy-reports
        execute_chef_run_list(solo_config_base=solo_config_base, run_list=["recipe[genomics::_galaxy_reports]"])
    elif options.update_type =="volume":
        # replace volume
        assert options.volume_name != None
        volumes_info = instance_config["volumes"]
        assert options.volume_name in volumes_info
        volume_info = volumes_info[options.volume_name]
        # make sure nfs is off
        print "stoping nfs-kernel-server ..."
        command = "service nfs-kernel-server stop"
        subprocess.call(command, shell=True)
        detach_volume(volume_info=volume_info, instance_aws_info=instance_aws_info)
        create_volume(volume_name=options.volume_name, 
                      volume_info=volume_info,
                      releases_config=releases_config,
                      main_config=main_config,
                      instance_config=instance_config,
                      instance_aws_info=instance_aws_info )
        # start nfs
        print "starting nfs-kernel-server ..."
        command = "service nfs-kernel-server start"
        subprocess.call(command, shell=True)
    elif options.update_type =="release_update":
        # reinstall Galaxy 
        reinstall_galaxy(main_config=main_config,
                         instance_config=instance_config,
                         releases_config=releases_config,
                         backup_galaxy=options.backup_galaxy,
                         creds_config=creds_config,
                         node_name_short=node_name_short,
                         solo_config_base=solo_config_base)
        # replace volumes
        volumes_info = instance_config["volumes"]
        # make sure nfs is off
        print "stoping nfs-kernel-server ..."
        command = "service nfs-kernel-server stop"
        subprocess.call(command, shell=True)
        for volume_name, volume_info in volumes_info.iteritems():
            # skip scratch_volume
            if volume_name != "scratch_volume":
                detach_volume(volume_info=volume_info, instance_aws_info=instance_aws_info)
                create_volume(volume_name=volume_name, 
                              volume_info=volume_info,
                              releases_config=releases_config,
                              main_config=main_config,
                              instance_config=instance_config,
                              instance_aws_info=instance_aws_info )
        # start nfs
        print "starting nfs-kernel-server ..."
        command = "service nfs-kernel-server start"
        subprocess.call(command, shell=True)
    else:
        sys.exit("update type not supported.")

# test-function action
if options.action == "test-function":
    configure_galaxy_ini(main_config=main_config, instance_config=instance_config, creds_config=creds_config, node_name_short=node_name_short)
