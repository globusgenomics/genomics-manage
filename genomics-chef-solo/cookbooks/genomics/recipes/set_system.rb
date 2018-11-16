
# set up hostname and install some packages
cleaned_name = node.name.gsub('_', '-')

node.normal['system']['short_hostname'] = cleaned_name.split('.')[0]
dotindex = cleaned_name.index('.')
if dotindex.nil?
  node.normal['system']['domain_name'] = 'globusgenomics.org'
else
  node.normal['system']['domain_name'] = cleaned_name[(dotindex+1)..-1]
end

node.normal['system']['packages']['install'] = [
    "mailutils",
    "mc",
    "ntp"
]

include_recipe "system::default"
include_recipe "apt::default"
