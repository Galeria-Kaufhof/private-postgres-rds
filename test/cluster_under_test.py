import logging
import subprocess
import unittest
from conf import OrganizationConf
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
    zone = OrganizationConf.test_zone()
    db_instance_name = 'test'

    INITIAL_MASTER = "192.168.121.101"
    INITIAL_SLAVE  = "192.168.121.102"
    SERVER3 = "192.168.121.103"
    SERVER4 = "192.168.121.104"
    service_url = OrganizationConf.service_url(zone, db_instance_name)
    credentials_folder = "test-credentials"
    admin_password = "Baequahci6la"
#~    admin_password = open("{folder}/psql/{zone}/{name}/admin_password".format(
#~        folder=credentials_folder, zone=zone, name=db_instance_name)).read().strip()
#~    admin_password = open("{folder}/admin_password".format(
#~        folder=credentials_folder, name=db_instance_name)).read().strip()
#~    backuper_aws_credentials = \
#~            "{folder}/backup/backuper-{name}-{zone}.credentials.sh".format(
#~                    folder=credentials_folder, zone=zone, name=db_instance_name)
#~    backup_configurer_aws_credentials = \
#~            "{folder}/backup/dev/configurer.credentials.sh".format(
#~                    folder=credentials_folder, zone=zone, name=db_instance_name)

    @classmethod
    def service_url_filename(cls):
        return "{}/test/state/postgres-service-endpoint.txt".format(project_path)

    @classmethod
    def readonly_service_url_filename(cls):
        return "{}/test/state/readonly-postgres-service-endpoint.txt".format(project_path)

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
            raise Exception("No server registered under service_url")

t = unittest.TestCase('__init__') # just use for assertions

