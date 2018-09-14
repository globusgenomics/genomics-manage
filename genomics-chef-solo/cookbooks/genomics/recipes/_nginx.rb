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

# set pid file loc to match package install
node.set['nginx']['pid'] = '/run/nginx.pid'
node.set['nginx']['worker_processes'] = 4
node.set['nginx']['gzip'] = "on"
node.set['nginx']['gzip_vary'] = "on"
node.set['nginx']['gzip_comp_level'] = 6
node.set['nginx']['gzip_proxied'] = "any"
node.set['nginx']['gzip_buffers'] = "16 8k"
node.set['nginx']['gzip_http_version'] = "1.1"

include_recipe "nginx"

# set username/passwd for galaxy reports
secret = Chef::EncryptedDataBagItem.load_secret(::File.join(node["genomics_manage_dir"], 'encrypted_data_bag_secret'))
galaxy_reports_user = Chef::EncryptedDataBagItem.load("nginx", "galaxy_reports_user", secret)
package "apache2-utils" do
end
execute "htpasswd user" do
  command  "htpasswd -cb /etc/nginx/galaxy-reports.htpasswd #{galaxy_reports_user['username']} #{galaxy_reports_user['passwd']}"
  not_if   { ::File.exists?("/etc/nginx/galaxy-reports.htpasswd")}
end
file "/etc/nginx/galaxy-reports.htpasswd" do
  mode      0644
  only_if   { ::File.exists?("/etc/nginx/galaxy-reports.htpasswd")}
end

# cert
ssl_path = "/etc/letsencrypt/live/#{node.name}"

bash 'install cert' do
  user 'root'
  code <<-EOH
    apt-get update
    apt-get install -y software-properties-common
    add-apt-repository -y ppa:certbot/certbot
    apt-get update
    apt-get install -y python-certbot-nginx 
    certbot --nginx certonly --agree-tos -m #{node['genomics']['maintainer']['email']} -d #{node.name} -n
  EOH
  not_if { ::File.directory?(ssl_path)}
end

template "/etc/nginx/sites-available/galaxy" do
  source "nginx_galaxy.erb"
  mode      0644
  variables(
      :upstream_name => "#{node['system']['short_hostname']}_galaxy",
      :upstream_name_reports => "#{node['system']['short_hostname']}_galaxy_reports",
      :ssl_path => ssl_path
  )
  notifies :restart, 'service[nginx]', :delayed
end

link "/etc/nginx/sites-enabled/galaxy" do
  to "/etc/nginx/sites-available/galaxy"
  notifies :restart, 'service[nginx]', :delayed
end

# For IGV
directory "/usr/share/nginx/wwwTrue" do
  mode      0755
  recursive true
  action :create
end

link "/usr/share/nginx/wwwTrue/scratch" do
  to "/scratch"
  action :create
end
