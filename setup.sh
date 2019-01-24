#install condor
wget -qO - https://research.cs.wisc.edu/htcondor/ubuntu/HTCondor-Release.gpg.key | sudo apt-key add -
echo "deb http://research.cs.wisc.edu/htcondor/ubuntu/stable/ trusty contrib" >> /etc/apt/sources.list
apt-get update
apt-get install -y condor
dpkg -i genomics-chef-solo/chefdk_1.5.0-1_amd64.deb
apt-get install -y git
apt-get install -y nfs-kernel-server
apt-get install -y python-pip
apt-get install -y python-dev 
apt-get install -y libssl-dev
#pip install virtualenv
#virtualenv venv
#activate () {
#  . ${PWD}/venv/bin/activate
#}
#activate
pip install boto3 
pip install --upgrade requests
pip install --upgrade setuptools
pip install cryptography==2.2.2
pip install uwsgi
pip install supervisor