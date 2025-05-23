# -------------------------------------------------------------------------- #
# Copyright 2014-2015, University of Chicago                                 #
#                                                                            #
# Licensed under the Apache License, Version 2.0 (the "License"); you may    #
# not use this file except in compliance with the License. You may obtain    #
# a copy of the License at                                                   #
#                                                                            #
# http://www.apache.org/licenses/LICENSE-2.0                                 #
#                                                                            #
# Unless required by applicable law or agreed to in writing, software        #
# distributed under the License is distributed on an "AS IS" BASIS,          #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.   #
# See the License for the specific language governing permissions and        #
# limitations under the License.                                             #
# -------------------------------------------------------------------------- #


# Download and Install globus-connect-server
globus_deb = ::File.join(Chef::Config[:file_cache_path], "#{node['globus']['deb_name']}")

remote_file globus_deb do
  action    :create_if_missing
  source    node['globus']['deb_download_url']
  mode      0644
  not_if    { ::File.exists?(globus_deb) }
end

bash 'install globus-connect-server' do
  action :nothing
  user 'root'
  code <<-EOH
  dpkg -i #{globus_deb}
  apt-get update
  apt-get -y install globus-connect-server
  EOH
  subscribes :run, "remote_file[#{globus_deb}]", :immediately
end


# decrypt encrypted data bag

secret = Chef::EncryptedDataBagItem.load_secret(::File.join(node["genomics_sec_dir"], 'encrypted_data_bag_secret'))
globus_cred = Chef::EncryptedDataBagItem.load("globus", "globus_cred", secret)


cookbook_file "/etc/grid-security/grid-mapfile" do
  action    :create_if_missing
  source    "default-gridmap"
  mode      0644
end

ep_name = node['system']['short_hostname']

template "#{node['globus']['config_file']}" do
  source    "globus-connect-server.conf.erb"
  owner     "root"
  group     "root"
  mode      0644
  variables(
      :globus_username => globus_cred['username'],
      :globus_password => globus_cred['password'],
      :ep_name => ep_name
  )
end

bash 'add Globus endpoint' do
  action :nothing
  user 'root'
  code <<-EOH
  globus-connect-server-setup
  echo "!!!Please update the endpoint through Globus CLI (globus endpoint update ENDPOINT_ID --display-name galaxy##{ep_name} --managed --myproxy-server myproxy.globusonline.org)"
  sleep 2m
  EOH
  subscribes :run, "template[#{node['globus']['config_file']}]", :immediately
end

# Globus Connect Server starts a apache2 server, which uses port 80, it conclicts with Genomics's Nginx server
service 'apache2' do
  action :stop
end
