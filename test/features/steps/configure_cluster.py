#!/usr/bin/env python2
from __future__ import print_function
from subprocess import call, check_call, check_output
import logging
import os
import subprocess
import time
from datetime import datetime
from behave import *
from cluster_under_test import *
from tasks import init_pg_servers_play_run
from execution import run_remotely

def run_ansible(context, more_vars=None):
    """Run ansible playbook for provided inventory file and redirect output
    including colors to a separate file. Run

    tail -f /tmp/detailed-test-output.txt

    in a separate terminal to observe ansible progress.
    """
    cmd = init_pg_servers_play_run(ClusterUnderTest.zone,
           ClusterUnderTest.db_instance_name, more_vars)
    run_with_details(cmd)

def run_with_details(cmd):
    """Execute command via shell, pretend to be a psedo-tty and save colorized output
    to a separate file for later analysis. Run

    tail -f /tmp/detailed-test-output.txt

    in a separate terminal to observe progress.
 
    """
    logging.info(cmd)
    check_call("""script -e -f -q /tmp/detailed-test-output.txt -c "{}" """.format(cmd),
            shell=True, stdout=open(os.devnull, 'w'))

@when(u'I initialize postgres cluster to {goal}')
def init_pg_servers(context, goal):
    run_ansible(context)

@when(u'I restore backup to a postgres cluster')
def step_impl(context):
    restore_step(context, pit=False)

@when(u'I run full backup')
def step_impl(context):
    run_remotely(host=ClusterUnderTest.INITIAL_MASTER, timeout=2592000, # wait forever
            command="sudo -u postgres /var/local/postgresql/full_backup_to_aws.sh >>/var/local/postgresql/log/backup.log 2>&1")

@when(u'I restore backup to a postgres cluster with remembered PIT')
def restore_step(context, pit=True):
    folder_latest = check_output("pyenv/bin/invoke restore_cluster {} {} | tail -1".format(
        ClusterUnderTest.zone, ClusterUnderTest.db_instance_name), shell=True)
    cmd = "pyenv/bin/invoke restore_cluster {} {} --backup-folder='{}'".format(
        ClusterUnderTest.zone, ClusterUnderTest.db_instance_name,
        folder_latest.strip())
    if pit:
        cmd += " --target-time '{}'".format(context.time_for_pit_recovery)
    run_with_details(cmd)

@when(u'I memorize current time for later PIT recovery')
def step_impl(context):
    context.time_for_pit_recovery = datetime.utcnow() # our servers including postgres use UTC

wipe_out_command = "systemctl stop postgresql.service; rm -rf /var/local/postgresql/data/"

@given('empty {servers}')
def empty_servers(context, servers):
    if servers == "master and slaves":
        wipe_out(context, "master")
        wipe_out(context, "slave")
        wipe_out(context, "SERVER3")
        wipe_out(context, "SERVER4")
    elif servers == "master":
        wipe_out(context, "master")
    elif servers == "slave":
        wipe_out(context, "slave")
    else:
        raise ValueError("Unsupported value for {servers}")

def host_for_node_name(node):
    if node == "master":
        return ClusterUnderTest.INITIAL_MASTER
    elif node == "slave":
        return ClusterUnderTest.INITIAL_SLAVE
    else:
        return getattr(ClusterUnderTest, node)

@when(u'I halt and wipe out the {node}') # master|slave supported
def wipe_out(context, node):
    run_remotely(host=host_for_node_name(node), command=wipe_out_command)

@given(u'a fresh postgres cluster')
def create_fresh_cluster(context):
    empty_servers(context, "master and slaves")
    init_pg_servers(context, "get new cluster")
    context.dbt.recreate_tables()

@when(u'I invoke migrate_to_master --target-master={target_master}')
def step_impl(context, target_master):
    cmd = "invoke migrate_to_master {} {} --target-master={}".format(
            ClusterUnderTest.zone, ClusterUnderTest.db_instance_name, host_for_node_name(target_master))
    run_with_details(cmd)

@then(u'service url should point to {node}')
def step_impl(context, node):
    expected = host_for_node_name(node)
    t.assertEqual(expected, ClusterUnderTest.resolve_service_url())

@when('I wait {number} seconds')
def wait_seconds(context, number):
    time.sleep(int(number))

@when('I wait {number} seconds to {goal}')
def step_impl(context, number, goal):
    wait_seconds(context, number)

@when(u'I reboot the {node}')
def step_impl(context, node):
    run_remotely(host=host_for_node_name(node), command="reboot")

@when('I wait for {node} to finish reboot')
def step_impl(context, node):
    start = time.time()
    while time.time() - start < 120:
        try:
            run_remotely(host=host_for_node_name(node), timeout=10, command="uptime")
            break
        except Exception:
            pass # ignore and retry

def get_inventory(context, hostgroup):
    cmd = "ZONE={} DB_INSTANCE_NAME={} {} ansible {} -i configure/pg-cluster-inventory.py --list-hosts"
    try:
        return check_output(cmd.format(
            ClusterUnderTest.zone, ClusterUnderTest.db_instance_name,
            context.extra_inventory_params, hostgroup),
            stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as ex:
        print(ex.output)
        print(open("/tmp/inventory.log").read())
        raise

@when(u"I use inventory extra params '{extras}'")
def step_impl(context, extras):
    extras = extras.replace('_SERVER4_', ClusterUnderTest.SERVER4)
    extras = extras.replace('_SERVER3_', ClusterUnderTest.SERVER3)
    extras = extras.replace('_INITIAL_SLAVE_', ClusterUnderTest.INITIAL_SLAVE)
    extras = extras.replace('_INITIAL_MASTER_', ClusterUnderTest.INITIAL_MASTER)
    context.extra_inventory_params = extras

@then(u'inventory {hostgroup} should fail')
def step_impl(context, hostgroup):
    with t.assertRaises(subprocess.CalledProcessError):
        get_inventory(context, hostgroup)

def assert_host_lists(expected_hosts, actual_hosts):
    """Produces more readable output than default assertEqual for list arguments"""
    t.assertEqual(" ".join(expected_hosts), " ".join(actual_hosts))

@then(u'inventory {hostgroup} should consist of {expected_elements}')
def step_impl(context, hostgroup, expected_elements):
    expected_hosts = [getattr(ClusterUnderTest, exp)  for exp in expected_elements.split(', ')]
    inv = get_inventory(context, hostgroup)
    # Example output:
    #   hosts (2):
    #     myzone-postgres-test-2.mydomain.example
    #     myzone-postgres-test-3.mydomain.example
    actual_hosts =  [s.strip() for s in inv.split("\n")[1:] if s]
    assert_host_lists(expected_hosts, actual_hosts)

@then(u'inventory {hostgroup} should be empty')
def step_impl(context, hostgroup):
    expected_hosts = []
    inv = get_inventory(context, hostgroup)
    print(inv)
    t.assertRegexpMatches(inv, '\[WARNING\]: No hosts matched, nothing to do')

