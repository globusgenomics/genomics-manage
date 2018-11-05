apt-get update
dpkg -i genomics-chef-solo/chefdk_1.5.0-1_amd64.deb
apt-get install -y git
apt-get install -y nfs-kernel-server
apt-get install -y python-pip
#pip install virtualenv
#virtualenv venv
#activate () {
#  . ${PWD}/venv/bin/activate
#}
#activate
pip install boto3 
pip install --upgrade requests
pip install --upgrade setuptools