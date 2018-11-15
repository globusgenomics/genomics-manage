name 'genomics'
maintainer 'Mark Xiao'
maintainer_email 'xiao2@uchicago.edu'
license 'All Rights Reserved'
description 'Installs/Configures genomics'
long_description 'Installs/Configures genomics'
version '0.1.0'
#chef_version '>= 12.1' if respond_to?(:chef_version)
depends          "system"
depends          "postfix"
depends          "nginx"
depends          "nfs"
depends          "users"
depends          "sudo"
depends          "globus"