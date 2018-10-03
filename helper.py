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


