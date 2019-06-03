"""
1. fill the args
2. python deploy.py
3. add the aws keys
4. check if the headnode role has the proper permissions, check the existing ones
5. add it to /var/spool/cron/crontabs/root: */2 * * * * python /opt/scripts/provisioner/manage_dynamic_pool.py >> /var/log/genomics/provision.log 2>>/var/log/genomics/provision.error.log
"""
from string import Template
import difflib

ssh_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDqdjILj7kHDM2AkDqmxBaFn2IiO5xLKL7He4V0hPgZn/xTtmWb15nhJTvjSkzOgDlb/g+RTWMBJHHXBxd1TZw9sn6U/D/ijlEz7i11hEUbVHww7wLChFjkX9FNL99dhLpTBJqF/KdIq32a+yjKgQYdOGMrnIIohCKzaKkCvGU72BjO/xRPuZ1MJp5qEUAjLt3hANX3HSRlNxKNmkbNxgSqDfypCtyaK0JL1Nosl0ZnzTrN7+Ba0gozngIQrCSp3KEL7WMk4/yUq7dwJ0UpREIPjU+PjMrmVukcXzOs2hrGMhvrEtj81IknHInkZNLivmm5Yb9001suDXmQ1RQrJoqp galaxy@ds.navipointgenomics.com"
private_ip = "172.25.255.196"
host_name = "ds.navipointgenomics.com"

# gg prod
az_to_subnet = {
    "us-east-1a": "subnet-824316af",
    "us-east-1b": "subnet-68221821",
    "us-east-1c": "subnet-79eaaa22",
    "us-east-1e": "subnet-f68d04ca"
}
security_group = "sg-193ba365"

domain_name = host_name[host_name.find(".") + 1 :]
instance_name = host_name[: host_name.find(".")]


def configure_file(template_file=None, file_path=None, config_info=None):
    template = open( template_file )
    src = Template( template.read() )
    updated_content = src.safe_substitute(config_info)
    with open(file_path, "r") as f:
        old_content = f.read()
    if old_content != updated_content:
        for text in difflib.unified_diff(old_content.split("\n"), updated_content.split("\n"), fromfile=file_path, tofile=file_path):
            print text
        with open(file_path, "w") as f:
            f.write(updated_content)

config_info = {
    "ssh_key": ssh_key,
    "private_ip": private_ip,
    "host_name": host_name,
    "domain_name": domain_name
}

configure_file(template_file="cloudinit.cfg", file_path="cloudinit.cfg", config_info=config_info)

config_info = {
    "ssh_key": ssh_key,
    "private_ip": private_ip,
    "host_name": host_name,
    "domain_name": domain_name
}

configure_file(template_file="cloudinit_0.cfg", file_path="cloudinit_0.cfg", config_info=config_info)

config_info = {
    "instance_name": instance_name,
    "az_to_subnet": az_to_subnet,
    "security_group": security_group
}

configure_file(template_file="manage_dynamic_pool.py", file_path="manage_dynamic_pool.py", config_info=config_info)

