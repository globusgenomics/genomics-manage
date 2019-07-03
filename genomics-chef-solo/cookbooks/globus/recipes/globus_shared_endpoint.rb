# Shared endpoint settings
# create shared dir
directory "#{node['genomics']['globus_sharing_endpoint']['shared_dir']}" do
  owner     "galaxy"
  group     "galaxy"
  mode      0755
  action    :create
end

secret = Chef::EncryptedDataBagItem.load_secret(::File.join(node["genomics_sec_dir"], 'encrypted_data_bag_secret'))
globus_cred = Chef::EncryptedDataBagItem.load("globus", "globus_sdk_cred", secret)

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

=begin
execute "create shared endpoint" do
  command "python /opt/scripts/create_globus_shared_endpoint_script.py"
end
=end