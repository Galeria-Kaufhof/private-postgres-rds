#!/usr/bin/env python
from __future__ import print_function
import contextlib
import os
import re
import sys

from invoke import task
from os import path

rds_path = path.dirname(path.abspath(__file__))
sys.path.insert(0, path.join(rds_path, 'lib'))
from sample_cluster_management import SampleClusterManagement

management = SampleClusterManagement()

ARGS_HELP = {
        'zone': "The corresponding network zone",
        'db-instance-name': "Short name of the db instance, e.g. bsna",
        'incremental-backup': "'on'/'off' for incremental backup facilitating point-in-time recovery",
        'target-master': "fqdn of the target master" }

@task(positional=[], help=ARGS_HELP)
def configure_cluster(ctx):
    """Initialize an empty cluster or update configuration of a running cluster.
    Implementation: runs the cluster configuration playbook."""
    ctx.run(management.playbook_cmd(), env=management.playbook_env(), pty=True, echo=True)

@task(positional=[], help=ARGS_HELP)
def migrate_to_master(ctx, target_master):
    """Helps with rolling upgrade. Typical case: replace master+slave by new,
    upgraded, replicated master+slave.
    Implementation: runs 3-step provisioning:
    * configure a new slave as replica of master
    * configure additional slave, using the just configured slave as upstream
    * promote the first new slave to master, deactivate old severs
    """
    def provision(more_vars):
        print("DEBUG ****** provision during migration ******* ", more_vars)
        ctx.run(management.playbook_cmd(more_vars), env=management.playbook_env(), pty=True, echo=True)

    provision({'ENFORCE_SLAVE_UPSTREAM': target_master}) # step 1, see docstring above
    # provision({'ENFORCE_SLAVE_UPSTREAM': target_master}) # step 2, TODO later: find out,
    #   what is needed on the secondary slave on promotion of the primary slave
    #   Check `recovery_target_timeline='latest'`
    provision({'ENFORCE_MASTER': target_master})         # step 3
    provision({}) # new solution: create the slave afterwards, new step 4

@task
def info_list(ctx):
    '''List all postgres related openstack VM instances.'''
    management.info_print_overview(management.get_host_info(
        inventory=management.test_inventory(),
        env=dict(os.environ)))

@task
def test_create_vagrant_cluster(ctx, recreate=False):
    '''Create a local vagrant cluster. --recreate enforces deletion of existing

    Both, VirtualBox (for best compatibility, works on both Mac and Linux)
    or libvirt (Linus only, better suited for continuous integration like Travis-CI) can be used.
    Prerequisites: vagrant-libvirt https://github.com/vagrant-libvirt/vagrant-libvirt#installation

    Once VMs created, you can `cd test` and run the usual vagrant commands
    like `vagrant status`, `vagrant ssh` to check VM status or inspect files
    inside VM.
    '''
    with ctx.cd(path.join(rds_path, 'test')):
        if recreate:
            ctx.run("vagrant destroy --force", pty=True)
        ctx.run("vagrant up pg01 --provision", pty=True)
        ctx.run("vagrant up pg02 --provision", pty=True)
        ctx.run("vagrant up pg03 --provision", pty=True)
        ctx.run("vagrant up pg04 --provision", pty=True)

@task(help={'scenario': """a single feature or even single scenario to run. Examples:
    --scenario "features/switchover.feature"
    --scenario "features/rolling-upgrade.feature -n 'manual, enforced switch-over'"
"""})
def test(ctx, scenario=None):
    '''Run functional tests against a test cluster. Create vagrant test cluster if needed.'''

    print("=== Starting unit tests - doctest ===")
    def run_doctest(name):
        p = path.join(rds_path, "lookup_plugins", name)
        ctx.run("python " + p, pty=True)

    run_doctest("compute_postgres_groups.py")

    print("=== Starting functional tests - scenarios ===")
    with ctx.cd(path.join(rds_path, 'test')):
        if scenario:
            ctx.run("behave {}".format(scenario), pty=True)
        else:
            ctx.run("behave features/add-slave.feature", pty=True)
            ctx.run("behave features/switchover.feature", pty=True)
            ctx.run("behave features/rolling-upgrade.feature", pty=True)
            ctx.run("behave features/inventory.feature", pty=True)
            ctx.run("behave features/credentials.feature", pty=True)
            return

            # ctx.run("behave backup_restore.feature", pty=True)

            return
            # TODO replace by generic call once all test scenarios work again
            ctx.run("behave features", pty=True)
