# backup logs from compute nodes and record their system usage
directory "#{node['monitoring']['monitor_compute_node']['log_dir']}" do
  owner     "root"
  group     "root"
  mode      0777
  action    :create
end

template "#{node['monitoring']['monitor_compute_node']['log_dir']}/compute_node_monitor.sh" do
  source    "compute_node_monitor.sh.erb"
  owner     "root"
  group     "root"
  mode      0755
end

template "#{node['monitoring']['monitor_compute_node']['log_dir']}/compute_node_monitor_clean_logs.py" do
  source    "compute_node_monitor_clean_logs.py.erb"
  owner     "root"
  group     "root"
  mode      0755
end

cron "compute_node_monitor_clean_logs" do
  minute    "0"
  hour      "0"
  weekday   "6"
  command   "#{node['monitoring']['monitor_compute_node']['log_dir']}/compute_node_monitor_clean_logs.py"
end

# nagios monitoring scripts

# install setup nagios nrpe client
package "nagios-nrpe-server" do
  action  :install
end

execute "nrpe-update-rc.d" do
  command   "useradd nrpe && update-rc.d nagios-nrpe-server defaults"
  only_if  { node['etc']['passwd']['nrpe'] == nil }
end

directory node['monitoring']['nagios_nrpe']['scripts_dir'] do
  owner     "root"
  group     "root"
  mode      0755
  action    :create
end

# monitor condor status
cookbook_file "#{node['monitoring']['nagios_nrpe']['scripts_dir']}/monitor_condor.py" do
  source    "nrpe_monitor_condor.py"
  owner     "root"
  group     "root"
  mode      0755
end

# monitor volume usage status
cookbook_file "#{node['monitoring']['nagios_nrpe']['scripts_dir']}/monitor_volume.py" do
  source    "nrpe_monitor_volume.py"
  owner     "root"
  group     "root"
  mode      0755
end

template node['monitoring']['nagios_nrpe']['config_file']  do
  source    "nrpe.cfg.erb"
  owner     "root"
  group     "root"
  mode      0644
end

execute "nrpe_restart" do
 command    "service nagios-nrpe-server restart"
 action     :run
end