# genomics-manage

Steps to launch a instance:
- Launch a ec2 instance as head node
    - select Ubuntu 14.04 as OS
    - select genomics-vpc VPC
    - select genomics-vpc-headnode subnet
    - select gg-head-node-role IAM role
    - increase root volume size to 15G
    - select genomics-vpc-headnode-sg security group
- Update the DNS with the instance's public ip
- Get the manage package
    - ssh to the instance and sudo su
    - install git: apt-get update; apt-get install -y git
    - git clone https://github.com/globusgenomics/genomics-manage.git
    - upload secret to the secret directory
- Install the prerequisites: sh setup.sh
- Check RDS if using RDS, that is make sure the database is available on RDS for this instance; Make sure the Globus Endpoint is not in use
- Run main.py to configure the instance, e.g. python main.py --action launch --instance test1.globusgenomics.org
- Setup globus creds at /home/galaxy/.globusgenomics
- Add it to Nagios monitoring: ssh to nagios.ops.globusgenomics.org, edit /etc/nagios3/conf.d/hosts.cfg and add the following, then sudo service nagios3 reload
```
define host {
  use server
  use prod-host
  address PRIVATE_IP
  host_name HOST_NAME_SHORT
  hostgroups all,genomics_server,linux,production
}
```
