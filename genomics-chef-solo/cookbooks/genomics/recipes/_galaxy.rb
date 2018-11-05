


# Shared endpoint settings
if node['genomics']['globus_sharing_endpoint']['use_globus_sharing_endpoint']
  # create shared dir
  directory "#{node['genomics']['globus_sharing_endpoint']['shared_dir']}" do
    owner     "galaxy"
    group     "galaxy"
    mode      0755
    action    :create
  end

  globus_cred = Chef::EncryptedDataBagItem.load("globus", "globus_sdk_cred")

  template "/home/galaxy/.globusgenomics/globus_transfer_cred" do
    source    "globus_transfer_cred.erb"
    owner     "galaxy"
    group     "galaxy"
    mode      0400
    variables(
      :client_id => globus_cred['client_id'],
      :access_token => globus_cred['access_token'],
      :scope => globus_cred['scope'],
      :expires_at_seconds => globus_cred['expires_at_seconds'],
      :token_type => globus_cred['token_type'],
      :refresh_token => globus_cred['refresh_token']
    )
  end

  # create shared endpoint script
  template "/opt/scripts/create_globus_shared_endpoint_script.py" do
    source    "create_globus_shared_endpoint_script.py.erb"
    mode      0644
  end

  execute "create shared endpoint" do
    command "python /opt/scripts/create_globus_shared_endpoint_script.py"
  end
end

# Install Galaxy

#Galaxy load balancing
package "build-essential"
package "python-dev"
python_pip 'uwsgi' do
  action    :install
end
python_pip 'supervisor' do
  action    :install
end


directory "#{node['galaxy']['dir']}" do
  owner     "galaxy"
  group     "galaxy"
  mode      0755
  action    :create
end

directory node['genomics']['logdir'] do
  owner     "galaxy"
  group     "galaxy"
  mode      0755
  action    :create
end


execute "untar galaxy source" do
  user          "galaxy"
  group         "galaxy"
  command       "tar -zxf #{galaxy_tarball} --strip-components=1 --directory #{node['galaxy']['dir']}"
  action        :nothing
end


if node['genomics']['galaxy']['repo_is_private']
  galaxy_source = "#{node['genomics']['galaxy']['repo']}/#{node['genomics']['galaxy']['revision']}"
  # get galaxy repo auth token
  galaxy_repo_user = Chef::EncryptedDataBagItem.load("galaxy", "galaxy_repo_user_1")
  auth_token = galaxy_repo_user['auth_token']

  bash 'download galaxy tarball with creds' do
    user 'root'
    code <<-EOH
    curl -H "Authorization: token #{auth_token}" -L #{galaxy_source} > #{galaxy_tarball}
    chmod 644 #{galaxy_tarball}
    EOH
    not_if { File.exist?(galaxy_tarball) }
    notifies :run, resources(:execute => "untar galaxy source"), :immediately
  end
else
  galaxy_source = "#{node['genomics']['galaxy']['repo']}/#{node['genomics']['galaxy']['revision']}.tar.gz"
  bash 'download galaxy tarball' do
    user 'root'
    code <<-EOH
    wget #{galaxy_source} -O #{galaxy_tarball}
    chmod 644 #{galaxy_tarball}
    EOH
    not_if { File.exist?(galaxy_tarball) }
    notifies :run, resources(:execute => "untar galaxy source"), :immediately
  end
end

cookbook_file "#{node['galaxy']['dir']}/galaxy-setup.sh" do
  source    "galaxy-setup.sh"
  owner     "galaxy"
  group     "galaxy"
  mode      0755
end


# load CLI credential from encrypted data bag to get the username used
globus_cred = Chef::EncryptedDataBagItem.load("globus", "globus_cred")

# organization specific settings
organization_info = data_bag_item("genomics_organizations", node['genomics']['organization']['organization_name'])

globus_group_id = organization_info["globus_group_id"]

# grab this key, defaulting to nil if absent
admin_users = organization_info["universe_wsgi_admin_users"] rescue nil

# get RDS username and passwd
rds_postgresql_user = Chef::EncryptedDataBagItem.load("aws_rds", "rds_postgresql_user")
rds_galaxy_username = rds_postgresql_user['username']
rds_galaxy_password = rds_postgresql_user['passwd']

template "#{node['galaxy']['dir']}/config/galaxy.ini" do
  source    "galaxy.ini.upgrading.erb"
  owner     "galaxy"
  group     "galaxy"
  mode      0644
  variables(
      :globus_username => globus_cred['username'],
      :name => node['system']['short_hostname'],
      :rds_galaxy_username => rds_galaxy_username,
      :rds_galaxy_password => rds_galaxy_password,
      :globus_group_id => globus_group_id,
      :admin_users => admin_users
  )
end

if not node['genomics']['dev_instance']
  # generate tool runners section by a helper function
  tool_runners = generate_galaxy_tool_runners

  template "#{node['galaxy']['dir']}/config/job_conf.xml" do
    source    "job_conf.xml.erb"
    owner     "galaxy"
    group     "galaxy"
    mode      0644
    variables(
        :tool_runners => tool_runners
    )
  end
end

# setup a script to update tool_conf_ci.xml
template "/opt/scripts/convert_tool_conf.py" do
  source "convert_tool_conf.py.erb"
  owner     "galaxy"
  group     "galaxy"
  mode 0644
end

#link "#{node['galaxy']['dir']}/config/tool_conf.xml" do
#  to    "#{node['galaxy']['dir']}/config/tool_conf_#{node['genomics']['galaxy']['universe']}.xml"
#end

# create some dirs if missing
directory "/scratch/galaxy/job_logs" do
  owner     "galaxy"
  group     "galaxy"
  mode      0755
  action    :create
end


# Setup Galaxy
execute "galaxy-setup.sh" do
  user      "galaxy"
  group     "galaxy"
  cwd       node['galaxy']['dir']
  command   "./galaxy-setup.sh"
  action    :run
end


# Configure supervisor
directory "/etc/supervisor" do
  owner     "root"
  group     "root"
  mode      0755
  action    :create
end

directory "/etc/supervisor/conf.d" do
  owner     "root"
  group     "root"
  mode      0755
  action    :create
end

directory "/var/log/supervisor" do
  owner     "root"
  group     "root"
  mode      0755
  action    :create
end

cookbook_file "/etc/supervisor/supervisord.conf" do
  source    "supervisord.conf"
  owner     "root"
  group     "root"
  mode      0644
end

template "/etc/supervisor/conf.d/galaxy.conf" do
  source    "supervisord_galaxy.conf.erb"
  owner     "root"
  group     "root"
  mode      0644
end

execute "supervisord_start" do
 command    "/usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf"
 action     :nothing
 subscribes :run, 'template[/etc/supervisor/conf.d/galaxy.conf]', :immediately
end

execute "supervisorctl_start" do
 command    "/usr/local/bin/supervisorctl -c /etc/supervisor/supervisord.conf"
 action     :nothing
 subscribes :run, 'template[/etc/supervisor/conf.d/galaxy.conf]', :immediately
end

execute "galaxy_start" do
 command    "supervisorctl start galaxy:"
 action     :nothing
 subscribes :run, 'execute[supervisorctl_start]', :immediately
end


# Restart Galaxy
if not node['genomics']['ops']['dont_restart_galaxy']
  execute "galaxy_restart" do
   command    "supervisorctl restart galaxy:"
   action     :run
  end
end
