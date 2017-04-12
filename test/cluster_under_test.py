import logging
import subprocess
import unittest
from conf import OrganizationConf

class ClusterUnderTest:
    """Settings for the cluster under test to use in connection strings etc."""
    zone = OrganizationConf.test_zone()
    db_instance_name = 'test'

    INITIAL_MASTER = OrganizationConf.server_name(zone, db_instance_name, 1)
    INITIAL_SLAVE  = OrganizationConf.server_name(zone, db_instance_name, 2)
    SERVER3 = OrganizationConf.server_name(zone, db_instance_name, 3)
    SERVER4 = OrganizationConf.server_name(zone, db_instance_name, 4)
    service_url = OrganizationConf.service_url(zone, db_instance_name)
    credentials_folder = "../postgres-credentials"
    admin_password = open("{folder}/psql/{zone}/{name}/admin_password".format(
        folder=credentials_folder, zone=zone, name=db_instance_name)).read().strip()
    backuper_aws_credentials = \
            "{folder}/backup/backuper-{name}-{zone}.credentials.sh".format(
                    folder=credentials_folder, zone=zone, name=db_instance_name)
    backup_configurer_aws_credentials = \
            "{folder}/backup/dev/configurer.credentials.sh".format(
                    folder=credentials_folder, zone=zone, name=db_instance_name)

    @classmethod
    def resolve_service_url(cls):
        # TODO Detect authorative DNS server
        # TODO Use expicit DNS server names only when running from developer comp,
        # on jenkins use default resolver - should still work
        logging.debug("----- reresolving -----")
        resolved = subprocess.check_output("dig +short {} {}".format(
            OrganizationConf.dns_authority(), ClusterUnderTest.service_url), shell=True)
        logging.debug("resolved: " + resolved)
        return resolved.split()[0][0:-1] # first line in dig output is host name with trailing '.'

t = unittest.TestCase('__init__') # just use for assertions

