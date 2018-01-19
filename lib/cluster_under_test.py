import logging
import subprocess
import unittest
import os
from os import path
project_path = path.dirname(path.dirname(path.abspath(__file__)))

class ClusterUnderTest:
    """Settings for the cluster under test to use in connection strings etc.
    This implementation of settings for a cluster under test is for local vagrant tests only.
    If you want to test with your real, e.g. OpenStack environment, inherit from this class
    and provide your own implementation for defining/storing credentials, like
    in Hashicorp's Vault, or your local git repository.
    """
    db_instance_name = 'test'

    if os.environ.get('RDS_TEST_USE_LIBVIRT'):
        INITIAL_MASTER = "192.168.121.101"
        INITIAL_SLAVE  = "192.168.121.102"
        SERVER3 = "192.168.121.103"
        SERVER4 = "192.168.121.104"
    else:
        INITIAL_MASTER = "192.168.44.101"
        INITIAL_SLAVE  = "192.168.44.102"
        SERVER3 = "192.168.44.103"
        SERVER4 = "192.168.44.104"
    credentials_folder = "test-credentials"
    admin_password = "test-Baequahci6la"
    replicator_password = "test-doh6Ohph1um9"

    @classmethod
    def service_url_filename(cls):
        return "{}/test/state/postgres-service-endpoint".format(project_path)

    @classmethod
    def readonly_service_url_filename(cls):
        return "{}/test/state/readonly-postgres-service-endpoint".format(project_path)

    @classmethod
    def remove_file_safe(cls, path_to_del):
        if os.path.exists(path_to_del):
            os.remove(path_to_del)

    @classmethod
    def clean_service_urls(cls):
        cls.remove_file_safe(cls.service_url_filename())
        cls.remove_file_safe(cls.readonly_service_url_filename())

    @classmethod
    def resolve_service_url(cls):
        # In vagrant test environment we use a simple text file to store the
        # current master or a list of read-only instances.
        # Possible extension: add a server with BIND installation to vagrant
        # and update service url via dynamic DNS or use consul to register the
        # service url.
        try:
            resolved = open(cls.service_url_filename()).read().strip()
            return resolved
        except IOError as ex:
            raise Exception("No server registered under service_url: " + str(ex))

t = unittest.TestCase('__init__') # just use for assertions

