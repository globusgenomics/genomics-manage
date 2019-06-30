#install condor
apt-get update
apt-get install -y libltdl7
apt-get install -y libvirt0
apt-get install -y libdate-manip-perl
apt-get install -y libpython2.7
apt-get install -y python
apt-get install -y bc
wget http://repo.globusgenomics.org/packages/condor_8.2.6-288241_amd64.deb
dpkg -i condor_8.2.6-288241_amd64.deb
dpkg -i genomics-chef-solo/chefdk_1.5.0-1_amd64.deb
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
pip install --upgrade pyopenssl
pip install cryptography==2.2.2
pip install uwsgi
pip install supervisor