#!/usr/bin/env python
from __future__ import print_function
import contextlib
import os
import re
import sys

from invoke import task
from os import path

sys.path.insert(0, path.abspath(path.join(__file__, '../lib')))
from conf import OrganizationConf, get_env

@task
def sync_virtualenv(ctx):
    """Create project specific python virtual environment in a subfolder.
    Install required ansible, openstack versions.
    """
    if not path.isfile("./pyenv/bin/pip"):
        ctx.run("virtualenv --no-site-packages --python=/usr/bin/python2.7 pyenv")
    ctx.run("PIP_DOWNLOAD_CACHE=/var/tmp/ ./pyenv/bin/pip install -r requirements.txt")
    print("""
    Installation completed. Please check any error messages above.

    If you are going to use `openstack` or ansible directly on the command line, run

    . ./pyenv/bin/activate

    or even add it to your ~/.bashrc
    """)

def credentials_store():
    return path.abspath(path.join(__file__, '../../postgres-credentials'))

@task(help={'aws-account':
    "We use different AWS accounts for development and production. Please select e.g. `dev` or `prod`"})
def once_organization_wide(ctx, aws_account):
    """Run this task once, organization wide, not per db instance.
    If you use different AWS accounts for dev and prod S3 backup buckets,
    you actually need to run it more than once - once for each account.
    See http://private-postgres-rds.readthedocs.io (TODO full url) to read more
    about security concepts for backup users and credentials.
    """
    ctx.run("ansible-playbook organization-once/configure-once.playbook.yaml -vv --extra-vars='credentials_store={} aws_account={}'".format(credentials_store(), aws_account), pty=True, echo=True)

def str_var_dict(var_dict=None):
    if var_dict == None:
        return ''
    else:
        return ' '.join(["{}={}".format(k, var_dict[k]) for k in var_dict]) # TODO escaping

def init_pg_servers_play_run(zone, db_instance_name, incremental_backup, more_vars=None, more_env_vars=None):
    if incremental_backup not in ["on", "off"]:
        raise ValueError("Only 'on', 'off' are supported as values for '--incremental-backup'")
    # load AWS credentials for backup_configurer user
    cred_file = "{}/backup/{}/configurer.credentials.properties".format(
            credentials_store(), OrganizationConf.backup_aws_account_for_zone(zone))
    aws_vars = open(cred_file).readlines()
    aws_env = ' '.join([var.strip() for var in aws_vars])

    cred = credentials_store()
    more = str_var_dict(more_vars)
    more_env = str_var_dict(more_env_vars)
    inventory = "configure/pg-cluster-inventory.py"
    return "{aws_env} ZONE={zone} {more_env} DB_INSTANCE_NAME={db_instance_name} ansible-playbook init_pg_servers.playbook.yaml --extra-vars='credentials_store={cred} zone={zone} db_instance_name={db_instance_name} incremental_backup={incremental_backup} {more}' -i {inventory} -vv".format(**locals())

ARGS_HELP = {
        'zone': "The corresponding network zone",
        'db-instance-name': "Short name of the db instance, e.g. bsna",
        'incremental-backup': "'on'/'off' for incremental backup facilitating point-in-time recovery",
        'target-master': "fqdn of the target master" }

@task(positional=[], help=ARGS_HELP)
def configure_cluster(ctx, zone, db_instance_name, incremental_backup):
    """Initialize an empty cluster or update configuration of a running cluster.
    Implementation: runs `init_pg_cluster` playbook."""
    ctx.run(init_pg_servers_play_run(zone, db_instance_name, incremental_backup),
        pty=True, echo=True)

@task(positional=[], help=ARGS_HELP)
def migrate_to_master(ctx, zone, db_instance_name, target_master, incremental_backup):
    """Helps with rolling upgrade. Typical case: replace master+slave by new,
    upgraded, replicated master+slave.
    Implementation: runs 3-step provisioning:
    * configure a new slave as replica of master
    * configure additional slave, using the just configured slave as upstream
    * promote the first new slave to master, deactivate old severs
    """
    def provision(more_env_vars):
        print("DEBUG ****** provision during migration ******* ", more_env_vars)
        ctx.run(init_pg_servers_play_run(zone, db_instance_name, incremental_backup,
            more_env_vars=more_env_vars), pty=True, echo=True)

    provision({'ENFORCE_SLAVE_UPSTREAM': target_master}) # step 1, see docstring above
    # provision({'ENFORCE_SLAVE_UPSTREAM': target_master}) # step 2, TODO later: find out,
    #   what is needed on the secondary slave on promotion of the primary slave
    #   Check `recovery_target_timeline='latest'`
    provision({'ENFORCE_MASTER': target_master})         # step 3
    provision({}) # new solution: create the slave afterwards, new step 4

def service_url(zone, db_instance_name):
    return OrganizationConf.service_url(zone, db_instance_name)

def backup_bucket_name(zone, db_instance_name):
    return OrganizationConf.backup_bucket_name(zone, db_instance_name)

@task(help={
    "from-zone": "by default the same as target zone",
    "from-db-instance": "by default the same as db-instance",
    "backup-folder": "subfolder in the backup bucket to use. Leave empty to list all the available backups",
    "target-time": """support for point in time recovery. Leave empty for latest or provide
    in format like '2017-03-22 15:50:12' Think about proper time zone. Our servers e.g. use UTC."""
    })
def restore_cluster(ctx, zone, db_instance, incremental_backup, from_zone=None, from_db_instance=None, backup_folder=None, target_time=None):
    """Configure and restore cluster from existing backup. Supports point-in-time recovery.

    invoke restore_cluster <zone> <db-instance> on
    invoke restore_cluster <zone> <db-instance> on --backup-folder='2017-03-22_10-27-58.928456401'
    """

    if from_zone == None:
        from_zone = zone
    if from_db_instance == None:
        from_db_instance = db_instance
    if backup_folder == None:
        get_env('AWS_SECRET_ACCESS_KEY', 'to list the backup buckets at AWS S3.')
        get_env('AWS_ACCESS_KEY_ID', 'to list the backup buckets at AWS S3.')
        get_env('AWS_REGION', 'to list the backup buckets at AWS S3.')
        print("Available values for --backup-folder :\n")
        res = ctx.run("aws s3 ls " + backup_bucket_name(from_zone, from_db_instance), pty=True, hide="stdout")
        for line in res.stdout.splitlines():
            print(re.search("PRE ([^ /]+)", line).group(1))
    else:
        recover_from = "{}/{}".format(backup_bucket_name(from_zone, from_db_instance), backup_folder)
        print("""
        Starting recovery
        """)
        more_vars = {'recover_from': recover_from, 'from_db_instance': from_db_instance, 'from_zone': from_zone}
        if target_time:
            more_vars['recovery_target_time'] = '"{}"'.format(target_time) # need quoting due to space char

        ctx.run(init_pg_servers_play_run(zone, db_instance, incremental_backup, more_vars=more_vars), pty=True, echo=True)

@task(help={'db-instance-name': "short name describing the instance"})
def initialize_servers(ctx, zone, db_instance_name):
    '''Install postgres from tar, set up system service. Keep data folder empty. Next step: configure_cluster'''
    for playbook in OrganizationConf.init_playbooks():
        var = "BASIC_INVENTORY=true ZONE={zone} DB_INSTANCE_NAME={db_instance_name} ".format(**locals())
        cmd = "pyenv/bin/ansible-playbook -i configure/pg-cluster-inventory.py -vv {}".format(playbook)
        ctx.run(var + cmd, pty=True)

@task
def info_list(ctx):
    '''List all postgres related openstack VM instances.'''
    ctx.run("RDS_ALL_ZONES=true configure/pg-cluster-inventory.py")

@task
def test_create_vagrant_cluster(ctx, recreate=False):
    '''Create a local vagrant-libvirt cluster. --recreate enforces deletion of existing
    Prerequisites: vagrant-libvirt https://github.com/vagrant-libvirt/vagrant-libvirt#installation'''
    if recreate:
        ctx.run("vagrant destroy --force", pty=True)
    ctx.run("vagrant up --provider=libvirt", pty=True)

@task
def test(ctx, test_inventory=None):
    '''Run functional tests against a test cluster. Create vagrant test cluster if needed.'''
    with ctx.cd('test'):
        if test_inventory == None: # use vagrant
            ctx.run("vagrant status")
        else:
            pass # TODO

