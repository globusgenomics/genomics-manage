# get RDS username and passwd

secret = Chef::EncryptedDataBagItem.load_secret(::File.join(node["genomics_sec_dir"], 'encrypted_data_bag_secret'))
rds_postgresql_user = Chef::EncryptedDataBagItem.load("aws", "rds_postgresql_user", secret)
rds_galaxy_username = rds_postgresql_user['username']
rds_galaxy_password = rds_postgresql_user['passwd']

# Configure Galaxy Reports Tool
template "#{node['galaxy']['dir']}/config/reports_wsgi.ini" do
  source    "reports_wsgi.ini.erb"
  owner     "galaxy"
  group     "galaxy"
  mode      0644
  variables(
      :rds_galaxy_username => rds_galaxy_username,
      :rds_galaxy_password => rds_galaxy_password,
  )

end

# Add init script for Galaxy Reports Tool
template "/etc/init.d/galaxy-reports" do
  source    "galaxy-reports.init.erb"
  mode      0755
  notifies  :run, "execute[update-rc.d(reports)]", :immediately
end

execute "update-rc.d(reports)" do
  command   "update-rc.d galaxy-reports defaults"
  action    :nothing
end

# create some dirs if missing
directory "/scratch/galaxy/files" do
  owner     "galaxy"
  group     "galaxy"
  mode      0755
  action    :create
end

# Start Galaxy Reports Tool
execute "galaxy-reports_restart" do
 command    "/etc/init.d/galaxy-reports restart"
 action     :run
 environment ({'PATH' => "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"})
end