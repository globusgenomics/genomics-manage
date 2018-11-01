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
