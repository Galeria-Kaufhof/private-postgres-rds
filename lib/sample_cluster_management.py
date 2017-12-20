#!/usr/bin/env python2
import json
import os
import sys
from tabulate import tabulate
from os import path
from cluster_under_test import *
from collections import defaultdict

project_path = path.dirname(path.dirname(path.abspath(__file__)))

class SampleClusterManagement():
    """You can inherit from this class to adjust for your own setup like:
    * your own inventory (OpenStack based, or OpenVZ, or AWS or libvirt)
    * your special environment requirements
    * your credentials handling (plain files, Vault or private git repository)
    Or copy and paste and use as inspiration.
    """

    def str_var_dict(self, var_dict=None):
        if var_dict == None:
            return ''
        else:
            return ' '.join(["{}={}".format(k, var_dict[k]) for k in var_dict]) # TODO escaping

    def test_inventory(self):
        if os.environ.get('RDS_TEST_USE_LIBVIRT'):
            return path.join(project_path, "test/vagrant_servers_libvirt")
        else:
            return path.join(project_path, "test/vagrant_servers_virtualbox")

    def playbook_cmd(self, more_vars={}):
        inventory = self.test_inventory()
        playbook = path.join(project_path, "playbooks/sample_configure_cluster.yaml")
        more = self.str_var_dict(more_vars)
        extra = "--extra-vars 'admin_password={} replicator_password={} {}'".format(
                ClusterUnderTest.admin_password, ClusterUnderTest.replicator_password, more)
        return "ansible-playbook {playbook} -f 1 -i {inventory} {extra} -vv".format(**locals())

    def playbook_env(self):
        env = dict(os.environ)
        env['ANSIBLE_FORCE_COLOR'] = 'true'
        env['ANSIBLE_ROLES_PATH'] = path.dirname(project_path)
        return env

    def get_env(self, key, reason="for this feature to work."):
        """Get a parameter value from environment variable and report error if value is missing"""
        if key in os.environ:
            return os.environ[key]
        else:
            raise ValueError("You need to provide {} env var {}".format(key, reason))

    def get_host_info(self, env=dict(os.environ)):
        """Return list of host-information. Every entry contains hostname and
        all the local postgres-related facts, e.g. upstream, DB size etc."""
        inventory = self.test_inventory()
        cmd = "ansible postgres --become --user root -f 14 -i {inventory} -m setup -a 'filter=ansible_local' -o".format(**locals())
        print(cmd); sys.stdout.flush()
        try:
            out = subprocess.check_output(cmd, env=env, shell=True)
        except subprocess.CalledProcessError as ex: # ignore, if some hosts not reachable
            out = ex.output
        hosts = []
        for line in out.strip().split("\n"):
            try:
                # example line:
                # 10preprod0000-postgres-media-1.10preprod0000.gkh-setu.de | SUCCESS => {"ansible_facts": {"ansible_local": {"pg": {"state": "CONFIGURED_SLAVE"}}}, "changed": false}
                left, json_data = line.split(" => ")
                full_hostname, success = left.split(" ", 1)
    #~            coordinates = parse_hostname(full_hostname)
    #~            cluster = "{stage}{tenant}-{serverrole}".format(**coordinates)
    #~            order = "{stage}{tenant}-{serverrole}-{dc}-{number}".format(**coordinates)
    #~            hostname = full_hostname # full_hostname.split(".")[0] # e.g. 10preprod0000-postgres-media-1.10preprod0000.gkh-setu.de => 10preprod0000-postgres-media-1
                data = json.loads(json_data)
                pg = data['ansible_facts']['ansible_local']['pg']
                hosts.append(defaultdict(lambda: '-', pg, hostname=full_hostname, order=full_hostname)) # cluster=cluster, order=order))
            except Exception as ex:
                print("Error '{}' processing line '{}'".format(ex, line))
                pass # just ignore this line/host - process remaining
        return hosts

    def info_print_overview(self, hosts_info): # hosts_info - array of host attributes
        srt = sorted(hosts_info, key=lambda h: h['order'])
        table = []
        for pg in srt:
            running = pg['running']
            if pg['upstream']:
                running += "\n" + pg['upstream']
            table.append([
                pg['hostname'], pg['state'], pg['mb_data_space'], pg['mb_db'],
                pg['mb_xlog'], pg['wal_keep'], running,
                pg['last_xlog'], pg['repl_delay'][0:13] ])
        print(tabulate(table, tablefmt="psql",
            headers=[
                "hostname", "state", "space\nMB", "base\nMB", "xlog\nMB",
                "WAL\nkeep", "running /\nupstream", "xlog\nposition", "repl\ndelay"]))

