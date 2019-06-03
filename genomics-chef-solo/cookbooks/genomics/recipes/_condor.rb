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


# _user_setup must run because it creates the ssh pubkey for the galaxy user,
# which is used in turn in the cloudinit template
#include_recipe "genomics::_user_setup"

# We cannot use apt_repository because it adds 'deb-src' that is not provided by the repo.
#file "/etc/apt/sources.list.d/condor.list" do
#  action    :create_if_missing
#  mode      0644
#  content   "deb [arch=amd64] http://www.cs.wisc.edu/condor/debian/stable/ wheezy contrib"
#  notifies  :run, "execute[apt-get update]", :immediately
#end

#package "condor" do
#  options "--force-yes"
#  action :install
#end

# create the condor service so that it can be notified
service "condor" do
  supports :status => true, :restart => true
  action [ :enable ]
end

execute "update-rc.d condor defaults" do
  user "root"
  group "root"
end

# Create EXECUTE directory. The directory is used by local STARTD must not
# be shared with other STARTD.

directory node[:genomics][:condor][:execute_dir] do
  mode 0755
  owner "condor"
  group "condor"
  recursive true
end

directory "/var/spool/condor" do
  mode 0755
  owner "condor"
  group "condor"
  recursive true
end

# Create the local configuration file.

template "/etc/condor/condor_config.local" do
  source "condor_config.erb"
  mode 0644
  owner "condor"
  group "condor"
  variables(
    :daemons => "COLLECTOR, MASTER, NEGOTIATOR, SCHEDD, STARTD"
  )
  notifies :restart, "service[condor]"
end

=begin
# Install scripts to manage condor pool

directory "/opt/scripts" do
  mode 0755
  action :create
end

template "/opt/scripts/cloudinit.cfg" do
  source "cloudinit.cfg.erb"
  mode 0644
end

# for instances under ec2 classic accounts, if it is in a VPC, when it requests spot price history, it should use a different name for product desccription
product_system_description = "Linux/UNIX"
classic_accounts_list = data_bag_item("other", "ec2_classic_accounts_list")["accounts_list"]
if classic_accounts_list.include?(node[:genomics][:aws][:account_id])
  product_system_description = "Linux/UNIX (Amazon VPC)"
end

package "ec2-api-tools"

template "/opt/scripts/manage_dynamic_pool.sh" do
  source "manage_dynamic_pool.sh.erb"
  mode 0755
  variables(
    :product_system_description => product_system_description
  )
  action :create
end

service "cron" do
  action :nothing
end

file "/etc/cron.d/manage_dynamic_pool" do
  action    :delete
end
cron "galaxy provisioner" do
  minute    "*/2"
  command   "/opt/scripts/manage_dynamic_pool.sh #{node['system']['short_hostname']} >> #{node['genomics']['provisioner']['logfile']} 2>>#{node['genomics']['provisioner']['error_logfile']}"
  notifies  :restart, "service[cron]"
end
=end
