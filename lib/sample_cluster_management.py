#!/usr/bin/env python2
import os
from os import path
from cluster_under_test import *

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

