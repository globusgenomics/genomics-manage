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
import fileinput
from pprint import pprint


def reinstall_galaxy(main_config=None,
                     instance_config=None,
                     releases_config=None,
                     backup_galaxy=False,
                     creds_config=None,
                     node_name_short=None,
                     solo_config_base=None):
    command = "supervisorctl stop galaxy:"
    subprocess.call(command, shell=True)
    if backup_galaxy:
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
    # update tool_data_table_conf.xml if necessary
    update_tool_data_table_conf(instance_config=instance_config)
    # update gg version num
    update_gg_version_in_welcome_page(main_config=main_config, instance_config=instance_config, releases_config=releases_config)
    # extra steps
    extra_steps(creds_config=creds_config, node_name_short=node_name_short)
    # run _galaxy recipe
    execute_chef_run_list(solo_config_base=solo_config_base, run_list=["recipe[genomics::_galaxy]"])
    # start galaxy-reports
    execute_chef_run_list(solo_config_base=solo_config_base, run_list=["recipe[genomics::_galaxy_reports]"])
    command = "supervisorctl start galaxy:"
    subprocess.call(command, shell=True)


def detach_volume(volume_info=None, instance_aws_info=None):
    # umount the volume
    command = "umount {0}".format(volume_info["mount_point"])
    print "{0} ...".format(command)
    subprocess.call(command, shell=True)
    # get the volume id
    client = boto3.client('ec2', region_name=instance_aws_info["aws_region"])
    response = client.describe_instances(InstanceIds=[instance_aws_info["instance_id"]])
    BlockDeviceMappings = response["Reservations"][0]["Instances"][0]["BlockDeviceMappings"]
    for i in BlockDeviceMappings:
        if i["DeviceName"] == volume_info["mount_device"]:
            volume_id = i["Ebs"]["VolumeId"]
            volume_status = i["Ebs"]["Status"]
            break
    # detach volume
    if volume_status == "attached":
        print "detaching volume {0} ...".format(volume_id)
        client.detach_volume(VolumeId=volume_id)
        # wait for the volume to be in available state
        while True:
            volume_response = client.describe_volumes(VolumeIds=[volume_id])
            volume_state = volume_response['Volumes'][0]['State']
            if volume_state == 'available':
                print ('volume {0} is in available state.'.format(volume_id))
                break
            else:
                print ('volume {0} is not in available state, wait for several seconds...'.format(volume_id))
                sleep(3)


def create_volume(volume_name=None, 
                  volume_info=None,
                  releases_config=None,
                  main_config=None,
                  instance_config=None,
                  instance_aws_info=None):
    if "snapshot_id" in volume_info:
        if volume_info["snapshot_id"] == "current_release":
            snapshot_id = releases_config[main_config["current_release"]]["snapshots"][volume_name]
        elif volume_info["snapshot_id"].startswith("release_"):
            release_num_tmp = volume_info["snapshot_id"]
            release_num = release_num_tmp[len("release_"):]
            snapshot_id = releases_config[release_num]["snapshots"][volume_name]
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

    aws_region = instance_aws_info["aws_region"]
    availability_zone = instance_aws_info["availability_zone"]
    instance_id = instance_aws_info["instance_id"]

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
    print "creating volume..."
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
        DEV_ORGANIZATIONS = ["dev", "dev1", "dev2", "test1", "test2", "test3", "test", "staging"]
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
    # hash based command: command = "git clone https://github.com/globusgenomics/genomics-galaxy-dev.git /opt/galaxy; cd /opt/galaxy; git checkout {0}".format(genomics_galaxy_version)
    repo, branch_name = get_gg_repo_and_branch(main_config=main_config, instance_config=instance_config, releases_config=releases_config)
    command = "git clone {0} --branch {1} --single-branch /opt/galaxy".format(repo, branch_name)
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
    if "galaxy" in instance_config and "tool_data_table_config_path" in instance_config["galaxy"]:
        tool_data_table_config_path = instance_config["galaxy"]["tool_data_table_config_path"]
    else:
        tool_data_table_config_path = "config/tool_data_table_conf.xml"
    if "galaxy" in instance_config and "len_file_path" in instance_config["galaxy"]:
        len_file_path = instance_config["galaxy"]["len_file_path"]
    else:
        len_file_path = "/mnt/galaxyIndices/galaxy/chrom"
    if "galaxy" in instance_config and "admin_users" in instance_config["galaxy"] and instance_config["galaxy"]["admin_users"] not in ["", None]:
        admin_users = main_config["galaxy"]["admin_users"] + "," + instance_config["galaxy"]["admin_users"]
    else:
        admin_users = main_config["galaxy"]["admin_users"]
    config_info = {
        "node_name_short": node_name_short,
        "globus_use_group": instance_config["globus"]["globus_use_group"],
        "globus_group_id": instance_config["globus"]["globus_group_id"],
        "database_connection": database_connection,
        "tool_data_path": tool_data_path,
        "tool_data_table_config_path": tool_data_table_config_path,
        "len_file_path": len_file_path,
        "admin_users": admin_users,
        "id_secret": creds_config.get("galaxy", "id_secret"),
        "welcome_url": instance_config["galaxy"]["welcome_url"],
        "smtp_server": creds_config.get("mail_system", "smtp_server"),
        "smtp_username": creds_config.get("mail_system", "smtp_username"),
        "smtp_password": creds_config.get("mail_system", "smtp_password"),
        "error_email_to": instance_config["galaxy"]["error_email_to"]
    }
    template = open( 'files/galaxy.ini.template' )
    src = Template( template.read() )
    updated_content = src.safe_substitute(config_info)
    file_path = "/opt/galaxy/config/galaxy.ini"
    with open(file_path, "r") as f:
        old_content = f.read()
    if old_content != updated_content:
        for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile="galaxy.ini", tofile="updated galaxy.ini"):
            print text
        with open(file_path, "w") as f:
            f.write(updated_content)
    update_file_ownership(file_path=file_path)


def configure_galaxy_job_conf(instance_config=None):
    # configure job_conf.xml
    file_path = "/opt/galaxy/config/job_conf.xml"
    updated_content = ""
    worker_num_cpus = instance_config["provisioner"]["worker"]["worker_num_cpus"]
    with open(file_path, "r") as f:
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
        with open(file_path, "w") as f:
            f.write(updated_content)
    update_file_ownership(file_path=file_path)


def configure_galaxy_tool_conf(node_name_short=None):
    # configure tool_conf.xml
    file_path = "/opt/galaxy/config/tool_conf.xml"
    updated_content = filter_tool_conf(node_name_short, file_path)
    with open(file_path, "r") as f:
        old_content = f.read()
    if old_content != updated_content:
        for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile="tool_conf.xml", tofile="updated tool_conf.xml"):
            print text
        with open(file_path, "w") as f:
            f.write(updated_content)
    update_file_ownership(file_path=file_path)

def mv_and_backup_galaxy():
    if not os.path.exists("/scratch/backup"):
        os.makedirs("/scratch/backup")
    command = "mv /opt/galaxy /scratch/backup/galaxy-{0}".format(datetime.datetime.today().strftime('%Y%m%d'))
    subprocess.call(command, shell=True)

def replaceAll(file,searchExp,replaceExp):
    for line in fileinput.input(file, inplace=1):
        if searchExp in line:
            line = line.replace(searchExp,replaceExp)
        sys.stdout.write(line)

def update_gg_version_in_welcome_page(main_config=None, instance_config=None, releases_config=None):
    branch_name = get_gg_repo_and_branch(main_config=main_config, instance_config=instance_config, releases_config=releases_config)[1]
    welcome_page = "/opt/galaxy" + instance_config["galaxy"]["welcome_url"]
    updated_content = '<td class="logo_table_row">{0}</td>'.format(branch_name)
    replaceAll(welcome_page, '<td class="logo_table_row"></td>', updated_content)
    update_file_ownership(file_path=welcome_page)

def update_tool_data_table_conf(instance_config=None):
    if instance_config["galaxy"]["tool_data_path"] != "tool-data":
        file_path = "/opt/galaxy/config/tool_data_table_conf.xml"
        search_content = "tool-data/"
        replace_content = "{0}/".format(instance_config["galaxy"]["tool_data_path"])
        replaceAll(file_path, search_content, replace_content)
        update_file_ownership(file_path=file_path)

def get_gg_repo_and_branch(main_config=None, instance_config=None, releases_config=None):
    genomics_galaxy_branch = instance_config["genomics_galaxy_version"]
    if "##" in genomics_galaxy_branch:
        tmp = genomics_galaxy_branch.split("##")
        genomics_galaxy_repo = tmp[0].strip()
        genomics_galaxy_branch = tmp[1].strip()
    else:
        if genomics_galaxy_branch == "current_release":
            genomics_galaxy_branch = releases_config[main_config["current_release"]]["galaxy_repo_branch"]
        elif genomics_galaxy_branch.startswith("release_"):
            release_num = genomics_galaxy_branch[len("release_"):]
            genomics_galaxy_branch = releases_config[release_num]["galaxy_repo_branch"]
        genomics_galaxy_repo = "https://github.com/globusgenomics/genomics-galaxy-dev.git"
    return (genomics_galaxy_repo, genomics_galaxy_branch)

def update_file_ownership(file_path=None, to_user="galaxy"):
    uid = pwd.getpwnam(to_user).pw_uid
    gid = grp.getgrnam(to_user).gr_gid
    os.chown(file_path, uid, gid)

def extra_steps(creds_config=None, node_name_short=None):
    # extra steps needed for specific requests
    # take care of eupathdb's tool's creds
    file_path = "/opt/galaxy/tools/eupath/Tools/config/config.json"
    if os.path.isfile(file_path) and node_name_short in ["eupathdb", "eupathdbstaging", "eupathdbdev"]:
        if node_name_short in ["eupathdb", "eupathdbstaging"]:
            config_info = {
                "url": creds_config.get("eupath_tool_cred", "url0")
                "user": creds_config.get("eupath_tool_cred", "user0"),
                "password": creds_config.get("eupath_tool_cred", "password0")
            }
        elif node_name_short in ["eupathdbdev"]:
            config_info = {
                "url": creds_config.get("eupath_tool_cred", "url1")
                "user": creds_config.get("eupath_tool_cred", "user1"),
                "password": creds_config.get("eupath_tool_cred", "password1")
            }
        else:
            sys.exit("instance is not supported")
        template = open( 'files/eupath_tool_config.template' )
        src = Template( template.read() )
        updated_content = src.safe_substitute(config_info)
        with open(file_path, "r") as f:
            old_content = f.read()
        if old_content != updated_content:
            for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile=file_path, tofile="updated file"):
                print text
            with open(file_path, "w") as f:
                f.write(updated_content)
        update_file_ownership(file_path=file_path)

