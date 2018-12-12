import boto3
from time import sleep
import sys
import subprocess
import re
import os
import pwd
import grp
import copy
from string import Template
import difflib
import datetime

def create_ec2_volume(region=None,
                      AvailabilityZone=None, 
                      Encrypted=None,
                      KmsKeyId=None,
                      Size=None,
                      SnapshotId=None,
                      VolumeType=None,
                      Tag=None,
                      InstanceId=None,
                      Device=None,
                      file_system=None,
                      mount_point=None,
                      mount_point_user=None ):
    client = boto3.client('ec2', region_name=region)

    # create volume
    if SnapshotId == None:
        SnapshotId = ''

    if Encrypted and KmsKeyId != None:
        response = client.create_volume(
                AvailabilityZone=AvailabilityZone, #'string',
                Encrypted=Encrypted, #True|False,
                #Iops=123,
                KmsKeyId=KmsKeyId, #'string',
                Size=Size, #123,
                SnapshotId=SnapshotId, #'string',
                VolumeType=VolumeType, #'standard'|'io1'|'gp2'|'sc1'|'st1',
                #DryRun=True|False,
                TagSpecifications=[
                    {
                        'ResourceType': 'volume',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': Tag
                            },
                        ]
                    },
                ])
    else:
        response = client.create_volume(
                AvailabilityZone=AvailabilityZone, #'string',
                #Encrypted=Encrypted, #True|False,
                #Iops=123,
                #KmsKeyId=KmsKeyId, #'string',
                Size=Size, #123,
                SnapshotId=SnapshotId, #'string',
                VolumeType=VolumeType, #'standard'|'io1'|'gp2'|'sc1'|'st1',
                #DryRun=True|False,
                TagSpecifications=[
                    {
                        'ResourceType': 'volume',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': Tag
                            },
                        ]
                    },
                ])

    volume_id = response['VolumeId']

    # wait for the volume to be created
    while True:
        volume_response = client.describe_volumes(VolumeIds=[volume_id])
        volume_state = volume_response['Volumes'][0]['State']
        if volume_state == 'available':
            print ('volume {0} is now available.'.format(volume_id))
            break
        else:
            print ('volume {0} is not available, wait for several seconds...'.format(volume_id))
            sleep(3)

    # attach the volume
    response = client.attach_volume(
            Device=Device,
            InstanceId=InstanceId,
            VolumeId=volume_id,
            #DryRun=True|False
            )
    
    # wait for the volume to be attached
    while True:
        volume_response = client.describe_volumes(VolumeIds=[volume_id])
        volume_state = volume_response['Volumes'][0]['Attachments'][0]['State']
        if volume_state == 'attached':
            print ('volume {0} is now attached.'.format(volume_id))
            break
        else:
            print ('volume {0} is not attached, wait for several seconds...'.format(volume_id))
            sleep(3)

    # make fs if volume is not created from a snapshot
    if SnapshotId == '' and file_system != None:
        if file_system == 'ext4':
            command = 'mkfs -t ext4 {0}'.format(Device.replace('sd', 'xvd'))
            subprocess.call(command, shell=True)
        else:
            sys.exit('File syetem type not supported.')
    
    #create the dir if it doesn't exist
    if not os.path.exists(mount_point):
        os.makedirs(mount_point)

    # update dir owner
    if mount_point_user != None:
        uid = pwd.getpwnam(mount_point_user).pw_uid
        gid = grp.getgrnam(mount_point_user).gr_gid
        os.chown(mount_point, uid, gid)

    # attach to dir
    to_insert = '{0} {1} auto rw,noatime 0 2\n'.format(Device.replace('sd', 'xvd'), mount_point)
    with open('/etc/fstab', 'r+') as f:
        for line in f:
            if line.startswith(to_insert):
                print 'Found line in fstab.'
                break
        else:
            f.write(to_insert)
    command = 'mount -a'
    subprocess.call(command, shell=True)



def filter_tool_conf(headnode, config_file):
    """
    filter the tool_conf.xml file according to organization tag
    take a config file and return the updated content
    """
    read_file = open(config_file, "r")
    result = ""

    def make_decision(line, headnode):
        DEV_ORGANIZATIONS = ["dev", "dev1", "dev2", "test1", "test2", "test3", "test"]
        if "organization_include=" in line and "organization_exclude=" in line:
            print "ERROR: organization_include and organization_exclude cannot present at the same time."
            print line
            sys.exit()
        elif "organization_include=" in line:
            comment = False
            tmp1 = line.split("organization_include=")
        elif "organization_exclude=" in line:
            comment = True
            tmp1 = line.split("organization_exclude=")
        else:
            print "ERROR: no organization_include or organization_exclude"
            sys.exit()

        tmp2 = tmp1[1].split("\"")
        tmp3 = tmp2[1].split(",")
        for i, e in enumerate(tmp3):
            tmp3[i] = e.strip()

        # skip the dev orgs
        if headnode in DEV_ORGANIZATIONS:
            comment = False
        elif headnode not in tmp3:
            comment = not comment

        return comment

    def exist_comments(line, c):
        if "<!--" in line:
            print "WARNING: comment symbol <!-- in the line to be commented"
            print "{0}: {1}".format(c, line)
            line = line.replace("<!--", "")
        if "-->" in line:
            print "WARNING: comment symbol --> in the line to be commented"
            print "{0}: {1}".format(c, line)
            line = line.replace("-->", "")
        return line

    l = [line for line in read_file.readlines()]
    c = 0
    file_length = len(l)

    while c < file_length:
        if "<!--" in l[c]:
            if "-->" in l[c].partition("<!--")[2]:
                result = result + l[c]
                c = c + 1
            else:
                result = result + l[c]
                c = c + 1
                while "-->" not in l[c]:
                    result = result + l[c]
                    c = c + 1
                    assert c < file_length
                result = result + l[c]
                c = c + 1

        elif "organization_include=" in l[c] or "organization_exclude=" in l[c]:
            if make_decision(l[c], headnode):
                if l[c].strip().startswith("<section") and \
                    l[c].strip().endswith(">") and \
                    not l[c].strip().endswith("/>"):
                    to_write = "<!-- " + exist_comments(l[c], c)
                    c = c + 1
                    assert c < file_length
                    while "</section>" not in l[c]:
                        to_write = to_write + exist_comments(l[c], c)
                        c = c + 1
                        assert c < file_length
                    if l[c].endswith("\n"):
                        to_write = to_write + exist_comments(l[c], c)[:-1] + " -->\n"
                    else:
                        to_write = to_write + exist_comments(l[c], c) + " -->"
                else:
                    if l[c].endswith("\n"):
                        to_write = "<!-- " + exist_comments(l[c], c)[:-1] + " -->\n"
                    else:
                        to_write = "<!-- " + exist_comments(l[c], c) + " -->"
                result = result + to_write
                c = c + 1
            else:
                result = result + l[c]
                c = c + 1
        else:
            result = result + l[c]
            c = c + 1

    read_file.close()
    return result


def execute_chef_run_list(solo_config_base=None, run_list=None):
    """
    accept solo config dict and run_list list to run
    """
    run_list = map(str.strip, run_list)
    to_write_copy = copy.deepcopy(solo_config_base)
    to_write_copy["run_list"] = run_list
    to_write_copy = str(to_write_copy).replace("\'", "\"").replace(": False", ": false").replace(": True", ": true")
    with open("solo_config.json", "w") as f:
        f.write(to_write_copy)
    command = "chef-solo -c solo.rb -j solo_config.json"
    subprocess.call(command, shell=True)


def demote(user_uid, user_gid):
    """Pass the function 'set_ids' to preexec_fn, rather than just calling
    setuid and setgid. This will change the ids for that subprocess only"""

    def set_ids():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return set_ids


def download_galaxy(main_config=None, instance_config=None, releases_config=None):
    genomics_galaxy_version = instance_config["genomics_galaxy_version"]
    if genomics_galaxy_version.startswith("branch/"):
        branch_name = genomics_galaxy_version.split("/")[1].strip()
        command = "git clone https://github.com/globusgenomics/genomics-galaxy-dev.git --branch {0} --single-branch /opt/galaxy".format(branch_name)
    else:
        if genomics_galaxy_version == "current_release":
            genomics_galaxy_version = releases_config[main_config["current_release"]]["galaxy_repo_commit_hash"]
        command = "git clone https://github.com/globusgenomics/genomics-galaxy-dev.git /opt/galaxy; cd /opt/galaxy; git checkout {0}".format(genomics_galaxy_version)
    subprocess.call(command, shell=True, preexec_fn=demote(pwd.getpwnam("galaxy").pw_uid, grp.getgrnam("galaxy").gr_gid))


def configure_galaxy_ini(main_config=None, instance_config=None, creds_config=None, node_name_short=None):
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


def configure_galaxy_job_conf(instance_config=None):
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


def configure_galaxy_tool_conf(node_name_short=None):
    # configure tool_conf.xml
    updated_content = filter_tool_conf(node_name_short, "/opt/galaxy/config/tool_conf.xml")
    with open("/opt/galaxy/config/tool_conf.xml", "r") as f:
        old_content = f.read()
    if old_content != updated_content:
        for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile="tool_conf.xml", tofile="updated tool_conf.xml"):
            print text
        with open("/opt/galaxy/config/tool_conf.xml", "w") as f:
            f.write(updated_content)

def mv_and_backup_galaxy():
    if not os.path.exists("/scratch/backup"):
        os.makedirs("/scratch/backup")
    command = "mv /opt/galaxy /scratch/backup/galaxy-{0}".format(datetime.datetime.today().strftime('%Y%m%d'))
    subprocess.call(command, shell=True)
