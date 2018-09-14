node_name "test1.globusgenomics.org"

current_dir = File.dirname(__FILE__)

file_cache_path "#{current_dir}/genomics-chef-solo/cache"
cookbook_path "#{current_dir}/genomics-chef-solo/cookbooks"
data_bag_path "#{current_dir}/genomics-chef-solo/data_bags"
role_path "#{current_dir}/genomics-chef-solo/roles"
solo true
