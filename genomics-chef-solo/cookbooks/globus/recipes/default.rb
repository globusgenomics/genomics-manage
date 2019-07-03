
# install globus-sdk
globus_sdk_dir = Chef::Config[:file_cache_path] + '/globus-sdk-python'
bash 'install globus-sdk' do
  user 'root'
  code <<-EOH
  mkdir #{globus_sdk_dir}
  git clone https://github.com/globus/globus-sdk-python.git #{globus_sdk_dir}
  cd #{globus_sdk_dir}
  python setup.py install
  EOH
  not_if { Dir.exist?(globus_sdk_dir) }
end

# globus genomics dir
directory "/home/galaxy/.globusgenomics" do
  owner     "galaxy"
  group     "galaxy"
  mode      0700
  action    :create
end

cookbook_file "/home/galaxy/.globusgenomics/globus_creds" do
  action    :create_if_missing
  source    "globus_creds"
  owner     "galaxy"
  group     "galaxy"
  mode      0400
end

cookbook_file "/home/galaxy/.globusgenomics/globus_user_granted_0" do
  action    :create_if_missing
  source    "globus_user_granted"
  owner     "galaxy"
  group     "galaxy"
  mode      0400
end

#include_recipe "globus::globus_endpoint" 