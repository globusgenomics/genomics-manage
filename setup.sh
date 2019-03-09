#install condor
apt-get update
wget http://repo.globusgenomics.org/packages/condor_8.2.6-288241_amd64.deb
dpkg -i condor_8.2.6-288241_amd64.deb
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