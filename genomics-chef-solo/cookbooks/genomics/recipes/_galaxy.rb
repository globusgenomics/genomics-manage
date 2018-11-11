
#Galaxy setup

directory node['galaxy']['dir'] do
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

cookbook_file "#{node['galaxy']['dir']}/galaxy-setup.sh" do
  source    "galaxy-setup.sh"
  owner     "galaxy"
  group     "galaxy"
  mode      0755
end

# create some dirs if missing
directory "/scratch/galaxy" do
  owner     "galaxy"
  group     "galaxy"
  mode      0755
  action    :create
end

directory "/scratch/galaxy/job_logs" do
  owner     "galaxy"
  group     "galaxy"
  mode      0755
  action    :create
end

directory "/scratch/galaxy/job_working_directory" do
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
