# json parsing is part of Chef, so no need to chef_gem it into place
# just require it to put it in scope
require 'json'
# open-uri is part of the standard lib -- people hate it, but it will do
require 'open-uri'

# the dynamic attribute in question contains the owning account ID
# this is always present, while the ownership of interfaces (the only place
# default chef ec2 metadata handling puts this ID) can get tricky in complex
# instance configurations
dynamic_doc_uri = "#{node[:genomics][:aws][:metadata_uri]}/dynamic/instance-identity/document"

# open the URI as a file, and parse the json body of the doc
jsonblob = open(dynamic_doc_uri) {|f| f.read }
jsonhash = JSON.load(jsonblob)

node.normal[:genomics][:aws][:account_id] = jsonhash['accountId']
node.normal[:genomics][:aws][:availability_zone] = jsonhash['availabilityZone']

