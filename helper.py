import boto3
from time import sleep
import sys
import subprocess
import re
import os
import pwd
import grp

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


def demote(user_uid, user_gid):
    """Pass the function 'set_ids' to preexec_fn, rather than just calling
    setuid and setgid. This will change the ids for that subprocess only"""

    def set_ids():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return set_ids