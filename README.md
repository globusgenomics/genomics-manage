# genomics-manage

Steps to launch an instance:
- Launch a ec2 instance as head node
    - select Ubuntu 14.04 as OS
    - select genomics-vpc VPC
    - select genomics-vpc-headnode subnet
    - select gg-head-node-role IAM role
    - increase root volume size to 15G
    - select genomics-vpc-headnode-sg security group
- Update the DNS with the instance's public ip
- Get the manage package
    - ssh to the instance
    - install git: sudo apt-get update; sudo apt-get install -y git
    - git clone https://github.com/globusgenomics/genomics-manage.git
    - upload secret to the secret directory
- Install the prerequisites as root: sh setup.sh
- Update tool_conf.xml on galaxy repo if necessary; Check RDS if using RDS, that is make sure the database is available on RDS for this instance; Make sure the Globus Endpoint is not in use
- Run main.py as root to configure the instance, e.g. python main.py --action launch --instance test1.globusgenomics.org
- Setup globus creds at /home/galaxy/.globusgenomics
- Optional: Add it to Nagios monitoring: ssh to nagios.ops.globusgenomics.org, edit /etc/nagios3/conf.d/hosts.cfg and add the following, then sudo service nagios3 reload
```
define host {
  use server
  use prod-host
  address PRIVATE_IP
  host_name HOST_NAME_SHORT
  hostgroups all,genomics_server,linux,production
}
```
- Optional: add galaxy-reports service, e.g. python main.py --action update --instance test1.globusgenomics.org --update-type galaxy-reports

Create config for an instance:
```
{
    # instance name
    "name": "test1.globusgenomics.org",
    # branch name or use current release at main.config which picks a release from releases.config, if you want to use a different repo, specify "repo##branch", such as "https://github.com/globusgenomics/genomics-galaxy-dev.git##dev"
    "genomics_galaxy_version": "current_release",
    # volumes to attach to the instance
    "volumes": {
        "scratch_volume": {
            # size in GB
            "size": 100,
            # if True, the volume will use the kms_key_id from aws section to encrypt the volume
            "encrypted": True,
            "volume_type": "gp2",
            # dir to mount to
            "mount_point": "/scratch",
            "mount_device": "/dev/sdf",
            "file_system": "ext4"
        },
        # Genomics Tools volume
        "galaxyTools": {
            "snapshot_id": "current_release",
            "volume_type": "gp2",
            "mount_point": "/mnt/galaxyTools",
            "mount_point_user": "galaxy",
            "mount_device": "/dev/sdz",
            "size": 30,
            "encrypted": False
        },
        # Genomics Indices volume
        "galaxyIndices": {
            "snapshot_id": "current_release",
            "volume_type": "gp2",
            "mount_point": "/mnt/galaxyIndices",
            "mount_point_user": "galaxy",
            "mount_device": "/dev/sdy",
            "size": 1130,
            "encrypted": False
        }
    },
    # dirs to export for nfs to share with the workers
    "nfs_export_dirs": ["/home/galaxy", "/opt/galaxy", "/mnt/galaxyTools", "/mnt/galaxyIndices", "/scratch"],
    # provisioner setup
    "provisioner": {
        # setup for workers
        "worker": {
            "worker_type": "r3.8xlarge",
            # bid price for spot instance
            "worker_bid_price": "3.00",
            "worker_num_cpus": "32",
            "worker_is_hvm": True,
            # merged ephemerals if there are more than one volumes come with the instance
            "merged_ephemerals": True
        },
        # use spot instance by default, so set this flag to True if use on demand instances
        "use_on_demand_instance": False
    },
    # database setup, 
    "database": {
        # use rds or local database
        "use_rds_postgresql_server": True
    },
    "globus": {
        # use globus group to restrict access
        "globus_use_group": True,
        # globus group used for login
        "globus_group_id": "920e3148-a6d3-11e2-8266-12313809f035"
    },
    "galaxy": {
        # specific which tool-data dir to use
        "tool_data_path": "tool-data",
        "len_file_path": "/mnt/galaxyIndices/galaxy/chrom",
        # extra admin users, seperate by ,
        "admin_users": "test@test.org",
        # choose which welcome page
        "welcome_url": "/static/welcome.html"
    },
    "aws": {
        # the kms key used to encrypt volumes
        "kms_key_id": "6272cd5d-362f-4b8d-8593-7f165d239c49",
        # all the subnets that the workers can be launched in
        "worker_subnets": {
            "us-east-1a": "subnet-824316af",
            "us-east-1b": "subnet-68221821",
            "us-east-1c": "subnet-79eaaa22",
            "us-east-1e": "subnet-f68d04ca"
        },
        "worker_security_group": "sg-193ba365"
    }
}
```
