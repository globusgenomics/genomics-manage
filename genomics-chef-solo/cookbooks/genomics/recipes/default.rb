#
# Cookbook:: genomics
# Recipe:: default
#
# Copyright:: 2018, The Authors, All Rights Reserved.

include_recipe "genomics::set_system"
include_recipe "genomics::set_ec2_metadata"
include_recipe "genomics::_user_setup"
include_recipe "globus"
#include_recipe "genomics::_postfix"
include_recipe "genomics::_nginx"
include_recipe "genomics::_condor"
include_recipe "genomics::_postgresql"