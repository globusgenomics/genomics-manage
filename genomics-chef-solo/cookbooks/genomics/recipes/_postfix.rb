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


node.set['postfix']['mail_type'] = 'client'
node.set['postfix']['main']['myhostname'] = node['system']['short_hostname']
node.set['postfix']['main']['mydomain'] = node['system']['domain_name']
node.set['postfix']['main']['mydestination'] = "$myhostname, $myhostname.$mydomain, localhost.$mydomain, localhost, localhost.localdomain"
# node.set['postfix']['main']['myorigin'] = '$myhostname.$mydomain'
node.set['postfix']['main']['myorigin'] = node['fqdn'] || node['hostname']
node.set['postfix']['main']['relayhost'] = 'smtp.globusgenomics.org'
node.set['postfix']['main']['smtp_use_tls'] = 'no'
node.set['postfix']['main']['smtp_tls_security_level'] = 'encrypt'
node.set['postfix']['main']['smtp_sasl_auth_enable'] = 'yes'
node.set['postfix']['aliases']['root'] = 'galaxy-info@ci.uchicago.edu'
node.set['postfix']['sasl_password_file'] = '/etc/postfix/sasl/passwd'
# needed to ensure clean execution of SASL recipe
node.set['postfix']['sasl']['smtp_sasl_user_name'] = "dummy_user"
node.set['postfix']['sasl']['smtp_sasl_passwd'] = "dummy_password"

include_recipe "postfix"


# plop the key/secret into /etc/postfix/sasl/passwd
# doing this after the sasl_auth recipe runs ensures that the encrypted databag
# data gets there
secret = Chef::EncryptedDataBagItem.load_secret(::File.join(node["genomics_sec_dir"], 'encrypted_data_bag_secret'))
ses_creds = Chef::EncryptedDataBagItem.load("postfix", "sasl_passwd", secret)
password_file = node['postfix']['sasl_password_file']

template password_file do
  mode      0600
  sensitive true
  source    'sasl_password_file.erb'
  variables(:user => ses_creds['smtp_sasl_user_name'],
            :password => ses_creds['smtp_sasl_passwd'])
  notifies  :run, 'execute[postmap-sasl_passwd]', :immediately
  notifies  :restart, 'service[postfix]'
end