# genomics-manage

Steps to launch a instance:
- Launch a ec2 instance as head node
    - select Ubuntu 14.04 as OS
    - select genomics-vpc VPC
    - select genomics-vpc-headnode subnet
    - select gg-head-node-role IAM role
    - increase root volume size to 15G
    - tag the instance
    - select genomics-vpc-headnode-sg security group
- Update the DNS with the instance's public ip
- Get the manage package
    - ssh to the instance and sudo su
    - install git: apt-get update; apt-get install -y git
    - git clone https://github.com/globusgenomics/genomics-manage.git
    - upload secret to the secret directory
- Install the prerequisites using setup.sh: sh setup.sh
- Check RDS if using RDS, that is make sure the database is available on RDS for this instance
- Run main.py to configure the instance, e.g. python main.py --action launch --instance test1.globusgenomics.org
- Setup globus creds at /home/galaxy/.globusgenomics
