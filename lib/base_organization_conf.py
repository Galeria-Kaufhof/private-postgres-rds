#!/usr/bin/env python2

class BaseOrganizationConf():
    """
    Contains organization specific naming conventions and urls.
    You can override as many methods as you wish in your own configuration.
    """
    @classmethod
    def domain(cls):
        return "example.com"

    @classmethod
    def server_name(cls, zone, db_instance_name, i):
        domain = cls.domain()
        return "{zone}-postgres-{db_instance_name}-{i}.{zone}.{domain}".format(**locals())

    @classmethod
    def server_name_filter(cls, zone, db_instance_name):
        return "{}-postgres-{}-".format(zone, db_instance_name)

    @classmethod
    def service_url(cls, zone, db_instance_name):
        domain = cls.domain()
        return "{db_instance_name}-postgres.{zone}.{domain}".format(**locals())

    @classmethod
    def backup_bucket_name(cls, zone, db_instance_name):
        BACKUP_BUCKET_TEMPLATE = "s3://backup--{service_url}"
        return BACKUP_BUCKET_TEMPLATE.format(service_url=cls.service_url(zone, db_instance_name))

    @classmethod
    def dns_authority(cls):
        return "@8.8.8.8"

    @classmethod
    def test_zone(cls):
        return "int"

    @classmethod
    def init_playbooks(cls):
        # relative to tasks.py in private-postgres-rds
        return ["buildimage/postgres.yaml"]

    @classmethod
    def installation_source(cls):
        return "https://get.enterprisedb.com/postgresql/postgresql-9.6.2-3-linux-x64-binaries.tar.gz"
