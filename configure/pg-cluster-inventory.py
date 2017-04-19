#!/usr/bin/env python2
"""
ansible dynamic inventory to support idempotent postgres cluster configuration for:

* initial cluster configuration
* a master switch over
* adding new servers to the cluster

Can be run one or multiple times and always detects the current master (if any)
or the desired master and all the slaves.
"""

from __future__ import print_function
from multiprocessing import Pool
from novaclient import client
from os import path
import json
import logging
import os
import re
import sys
import socket

logging.basicConfig(filename='/tmp/inventory.log', filemode='w', level=logging.INFO)
sys.path.insert(0, path.abspath(path.join(__file__, '../../lib')))

from execution import run_remotely
from conf import OrganizationConf

# logging.info('\n'.join(sys.path))
# logging.info('=============================================')

logging.info("============= Starting postgres inventory =================")
for var in sorted(os.environ):
    logging.debug(var + '=' + os.environ[var])
logging.info(sys.argv)

def get_env(key):
    """Get a parameter value from environment variable and report error if value is missing"""
    if key in os.environ:
        return os.environ[key]
    else:
        raise ValueError("You need to provide {} env var for the dynamic inventory to work".format(key))

def login_to_nova():
    return client.Client(
            version=2,
            username=get_env('OS_USERNAME'),
            password=get_env('OS_PASSWORD'),
            project_id=get_env('OS_TENANT_ID'),
            auth_url=get_env('OS_AUTH_URL'))

class State:
    NOT_REACHABLE = 1     # stop the inventory due insufficient data
    CONFIGURED_SLAVE = 2  # recovery.conf is present
    CONFIGURED_MASTER = 3 # no recovery.conf but postgresql.conf
    EMPTY_DATA_DIR = 4
    DEACTIVATED = 5       # e.g. after rolling upgrade, but the VM not deleted yet
    NOT_INITIALIZED = 6   # postgres is not installed yet
    UNKNOWN = None

def detect_state(server):
    try:
        lsres, status = run_remotely(host=server, command="/bin/ls -1 /var/local/postgresql/data", timeout=10)
        files = [f.strip() for f in lsres.split("\n")]
        if 'postgresql.conf.deactivated' in files:
            return State.DEACTIVATED
        elif 'recovery.conf' in files:
            return State.CONFIGURED_SLAVE
        elif 'postgresql.conf' in files:
            return State.CONFIGURED_MASTER
        elif status == 2:
            lsres, status = run_remotely(host=server, command="/bin/ls -1 /var/local/postgresql", timeout=10)
            if status == 2:
                return State.NOT_INITIALIZED
            else:
                return State.EMPTY_DATA_DIR
    except Exception as ex:
        print("ssh connect to '{}' failed!".format(server))
        return State.NOT_REACHABLE

def detect_ip(nova_server):
    netw = dict(nova_server.networks)
    del netw[u'private']
    if len(netw) > 1:
        raise Exception("Too many networks for server '{}': {}".format(nova_server.name, netw))
    elif len(netw) == 0:
        raise Exception("No networks found for server '{}'".format(nova_server.name))
    else:
        return netw.values()[0][0]

def str_state(state):
    if state == State.NOT_REACHABLE:
        return "NOT_REACHABLE"
    elif state == State.CONFIGURED_SLAVE:
        return "CONFIGURED_SLAVE"
    elif state == State.CONFIGURED_MASTER:
        return "CONFIGURED_MASTER"
    elif state == State.EMPTY_DATA_DIR:
        return "EMPTY_DATA_DIR"
    elif state == State.DEACTIVATED:
        return "DEACTIVATED"
    elif state == State.UNKNOWN:
        return "UNKNOWN"
    elif state == State.NOT_INITIALIZED:
        return "NOT_INITIALIZED"
    else:
        return '-----'

nova = login_to_nova()

def server_details(name):
    ip = detect_ip(servers[name])
    state = detect_state(ip)
    reboot = ""
    version = ""
    if state != State.NOT_REACHABLE:
        lsres, status = run_remotely(host=ip, command="/bin/ls -1 /run/reboot-required", timeout=10)
        if status == 0:
            reboot = "REBOOT!"
        lsres, status = run_remotely(host=ip, command="/usr/local/bin/pg_config --version", timeout=10)
        if status == 0:
            version = lsres.strip().split(" ")[1]
    res = "{:<15} {:17} {:7} {:5} {:<20} {}".format(
        ip, servers[name].flavor['id'], reboot, version, str_state(state), name)
    return res

if "RDS_ALL_ZONES" in os.environ:
    # Print list of servers, with IP and postgres configuration status in human readable form,
    # no json - not a valid ansible inventory output
    #
    # Example output:
    # 10.31.35.109    performance1-2            9.6.2 CONFIGURED_SLAVE     int-postgres-test-1.example.com
    # 10.31.35.180    performance1-2    REBOOT! 9.6.2 CONFIGURED_MASTER    int-postgres-test-2.example.com
    servers = {server.name : server for server in nova.servers.list(
        search_opts={'name': OrganizationConf.server_name_filter_all_zones()})}
    print("IP              Flavor            Require Ver   State                Hostname")
    p = Pool(20)
    details = p.map(server_details, sorted(servers.keys()))
    print("\n".join(details))
    sys.exit(0)

zone = get_env('ZONE')
db_instance_name = get_env('DB_INSTANCE_NAME')

def return_inventory(inv):
    print(json.dumps(inv, indent=2))
    sys.exit(0)

def name_filter():
    return OrganizationConf.server_name_filter(zone, db_instance_name)

if 'BASIC_INVENTORY' in os.environ:
    """Just list the postgres related servers, with IP addresses, for the basic provisioning"""
    res = {}
    res['postgres'] = []
    res['_meta'] = {}
    res['_meta']['hostvars'] = {}
    for server in nova.servers.list(search_opts={'name': name_filter()}):
        ip = detect_ip(server)
        res['postgres'].append(ip)
        res['_meta']['hostvars'][ip] = {"name": server.name}
    res['all'] = {
            'vars': {
                'installation_source': OrganizationConf.installation_source(),
            }
    }

    return_inventory(res)

servers = {server.name : State.UNKNOWN for server in nova.servers.list(
    search_opts={'name': name_filter()})}

if len(servers) == 0:
    raise Exception("No servers found with filter '{}'".format(name_filter()))

# Find out the configuration state of each server by checking the content of
# the /var/local/postgres/data folder
for server in servers.keys():
    servers[server] = detect_state(server)

logging.info(servers)

def detect(servers, state):
    """Returns a list of server names with desired state"""
    return sorted([name for name, st in servers.iteritems() if st == state])

if len(detect(servers, State.NOT_REACHABLE)) > 0:
    raise Exception("Some servers not reachable. Thus no reliable, comprehensive inventory available!")

candidates_master = detect(servers, State.CONFIGURED_MASTER)
if len(candidates_master) > 1:
    raise Exception("Danger: multiple configured masters detected: {}".format(candidates_master))
elif len(candidates_master) == 1:
    master = candidates_master[0]
else:
    candidates_slave = detect(servers, State.CONFIGURED_SLAVE)
    if len(candidates_slave) >= 1:
        master = candidates_slave[0]
    else:
        candidates_empty = detect(servers, State.EMPTY_DATA_DIR)
        master = candidates_empty[0]

slaves = []
deactivated = []
for server in servers.keys():
    if servers[server] == State.CONFIGURED_SLAVE or servers[server] == State.EMPTY_DATA_DIR:
        if server != master:
            slaves.append(server)
    if servers[server] == State.DEACTIVATED:
        deactivated.append(server)
slaves.sort()
deactivated.sort()

slave_upstream = master

# see rolling-cluster-upgrade.txt for details
if 'ENFORCE_SLAVE_UPSTREAM' in os.environ:
    enforce_upstream = os.environ['ENFORCE_SLAVE_UPSTREAM']
    if not enforce_upstream in servers.keys():
        raise ValueError("Desired ENFORCE_SLAVE_UPSTREAM '{}' is not found in the server list '{}'".format(
            enforce_upstream, servers.keys()))
    if servers[enforce_upstream] == State.EMPTY_DATA_DIR:
        # on this run only let the new intermediate upstream configure and finish replication,
        # do not provision further slaves now - do it on next run
        slaves = [enforce_upstream]
    else:
        # otherwise let all slaves provision normally
        slave_upstream = enforce_upstream # override
    master = None

# see rolling-cluster-upgrade.txt for details
deactivate = []
if 'ENFORCE_MASTER' in os.environ:
    enforce_master = os.environ['ENFORCE_MASTER']
    if not enforce_master in servers.keys():
        raise ValueError("Desired ENFORCE_MASTER '{}' is not found in the server list '{}'".format(
            enforce_master, servers.keys()))
    if master != enforce_master:
        deactivate.append(master)
        master = enforce_master
        slave_upstream = enforce_master # override
        if master in slaves:
            slaves.remove(master)
    for slave in slaves: # detect obsolete slaves with obsolete upstream
        conninfo, status = run_remotely(host=slave, command="cat /var/local/postgresql/data/recovery.conf | grep primary_conninfo", timeout=10)
        match_upstream = re.search(r'host=(\S+)', conninfo)
        if match_upstream and match_upstream.group(1) != enforce_master:
            logging.info('match_upstream:' + match_upstream.group(1))
            logging.info('  vs. ' + enforce_master)
            deactivate.append(slave)
    # clean up slave list
    for x in deactivate:
        if x in slaves:
            slaves.remove(x)

if (master in deactivated) or (master in deactivate):
    master = None

res = {}
res['aws_commands_host'] = ['localhost']
if master:
    res['master'] = [master]
if slaves:
    res['slaves'] = slaves
if deactivated:
    res['deactivated'] = deactivated
if deactivate:
    res['deactivate'] = deactivate

res['_meta'] = {}
res['_meta']['hostvars'] = {
        'localhost': {
            'ansible_connection': 'local',
            'ansible_python_interpreter': path.abspath(path.join(__file__, '../../pyenv/bin/python')),
        }
    }
res['all'] = {
        'vars': {
            'postgres_service_domain': OrganizationConf.service_url(zone, db_instance_name),
        }
    }

# set slave_upstream for all slaves, but it will be only applied on empty ones
for slave in slaves:
    res['_meta']['hostvars'].setdefault(slave, {})['slave_upstream'] = slave_upstream

return_inventory(res)

