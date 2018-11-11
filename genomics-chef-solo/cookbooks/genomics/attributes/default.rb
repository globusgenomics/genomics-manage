# for pulling down metadata
# no trailing slash
default['genomics']['aws']['metadata_uri'] = 'http://169.254.169.254/latest'

default['galaxy']['homedir'] = '/home/galaxy'
default['galaxy']['dir'] = '/opt/galaxy'
default['genomics']['logdir'] = '/var/log/genomics/'

default['genomics']['galaxy']['port'] = 8080
default['genomics']['galaxy']['reports']['port'] = 8081

default['genomics']['maintainer']['email'] = 'xiao2@uchicago.edu'

default['genomics']['condor']['execute_dir'] = '/ephemeral/0/condor'

default['genomics']['provisioner']['worker_pv_ami'] = 'ami-d85e75b0'
default['genomics']['provisioner']['worker_hvm_ami'] = 'ami-d05e75b8'

default['genomics']['aws']['worker']['keypair_name'] = 'galaxy'

default['monitoring']['monitor_compute_node']['log_dir'] = '/scratch/compute_nodes_logs'

default['genomics']['logdir'] = '/var/log/genomics/'
default['genomics']['galaxy']['logfile'] = ::File.join(node['genomics']['logdir'], 'galaxy.log')
default['genomics']['provisioner']['logfile'] = ::File.join(node['genomics']['logdir'], 'provision.log')
default['genomics']['provisioner']['error_logfile'] = ::File.join(node['genomics']['logdir'], 'provision.error.log')

default['genomics']['globus_sharing_endpoint']['shared_dir'] = '/scratch/shared'