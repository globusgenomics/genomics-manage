# FIXME:
# group and user must have gid and uid both pegged at 4000
group "galaxy" do
  gid       4000
end

# use manage_home=>true to ensure that homedir is created if missing
user "galaxy" do
  home      node['galaxy']['homedir']
  supports  :manage_home => true
  shell     '/bin/bash'
  uid       4000
  gid       4000
end


# generate a key for galaxy user

# key lives in .ssh dir under typical name
key_dir = ::File.join(node['galaxy']['homedir'], ".ssh")
key_file = ::File.join(key_dir, "id_rsa")

# create the key dir and set its perms to satisfy OpenSSH
directory key_dir do
  action    :create
  recursive true
  owner     'galaxy'
  group     'galaxy'
  mode      0700
end

# ssh-keygen only if the file hasn't already been created
# no need to explicitly set perms since ssh-keygen is part of the OpenSSH suite
# and will do it for us
execute "generate galaxy user RSA keypair" do
  not_if    { ::File.exists?(key_file) }
  user      'galaxy'
  command   "ssh-keygen -N \"\" -f #{key_file}"
end