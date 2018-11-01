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

database_name = "galaxy_#{node['system']['short_hostname']}"

#package "postgresql-client-common"
#package "postgresql"

bash 'install postgresql 9.4' do
  user 'root'
  code <<-EOH
	sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
	wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
	apt-get update
	apt-get install -y postgresql-9.4 pgadmin3
  EOH
end

# psycopg2 is required for Galaxy while it uses RDS
package 'python-psycopg2' do
	  action    :install
end

if not node['database']['use_rds_postgresql_server']
	# use local postgresql server
	galaxy_username = 'galaxy'
	galaxy_password = 'galaxy'
	# Create postgresql user
	bash "setup galaxy database" do
	  not_if "psql #{database_name} postgres -c ''", :user => 'postgres'
	  user "postgres"
	  code <<-EOH
	  createuser -D -S -R #{galaxy_username}
	  psql -c "alter user #{galaxy_username} with encrypted password '#{galaxy_password}';"
	  createdb "#{database_name}"
	  psql -c "grant all privileges on database #{database_name} to #{galaxy_username};"
	  EOH
	end
end

