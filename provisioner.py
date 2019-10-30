from helper import *
import os

def deploy_provisioner(instance_aws_info=None, node_name=None, node_name_short=None, domain_name=None, instance_config=None, creds_config=None):
    provisioner_dir = "/opt/scripts/provisioner"

    ssh_key_path = "/home/galaxy/.ssh/id_rsa.pub"

    cron_file = "/var/spool/cron/crontabs/root"

    with open(ssh_key_path, "r") as f:
        ssh_key = f.read().strip()

    if not os.path.exists(provisioner_dir):
        os.makedirs(provisioner_dir)

    # get volume mounting information
    volume_mounting_info = ""
    mounting_template = " - [ mkdir, -p, {1} ]\n - echo '{0}:{1} {1} nfs4 auto 0 0' >> /etc/fstab\n"
    for i in instance_config["nfs_export_dirs"]:
        volume_mounting_info = volume_mounting_info + mounting_template.format(instance_aws_info["private_ip"], i)

    config_info = {
        "ssh_key": ssh_key,
        "private_ip": instance_aws_info["private_ip"],
        "host_name": node_name,
        "domain_name": domain_name,
        "volume_mounting_info": volume_mounting_info
    }
    file_path = os.path.join(provisioner_dir, "cloudinit.cfg")
    configure_file_template(template_file="files/provisioner/cloudinit.cfg", file_path=file_path, config_info=config_info)

    config_info = {
        "ssh_key": ssh_key,
        "private_ip": instance_aws_info["private_ip"],
        "host_name": node_name,
        "domain_name": domain_name,
        "volume_mounting_info": volume_mounting_info
    }
    file_path = os.path.join(provisioner_dir, "cloudinit_0.cfg")
    configure_file_template(template_file="files/provisioner/cloudinit_0.cfg", file_path=file_path, config_info=config_info)

    config_info = {
        "instance_name": node_name_short,
        "az_to_subnet": instance_config["aws"]["worker_subnets"],
        "security_group": instance_config["aws"]["worker_security_group"],
        "ses_aws_access_key_id": creds_config.get("ses_iam", "aws_access_key_id"),
        "ses_aws_secret_access_key": creds_config.get("ses_iam", "aws_secret_access_key")
    }
    file_path = os.path.join(provisioner_dir, "manage_dynamic_pool.py")
    configure_file_template(template_file="files/provisioner/manage_dynamic_pool.py", file_path=file_path, config_info=config_info)
    file_path = os.path.join(provisioner_dir, "manage_dynamic_pool_ondemand.py")
    configure_file_template(template_file="files/provisioner/manage_dynamic_pool_ondemand.py", file_path=file_path, config_info=config_info)
    
    to_insert = "*/2 * * * * python /opt/scripts/provisioner/manage_dynamic_pool.py >> /var/log/genomics/provision.log 2>>/var/log/genomics/provision.error.log\n"
    if os.path.exists(cron_file):
        with open(cron_file, 'r+') as f:
            for line in f:
                if line.startswith(to_insert):
                    print 'Found line in /etc/exports.'
                    break
            else:
                f.write(to_insert)
    else:
        with open(cron_file, 'w') as f:
            f.write(to_insert)
            
