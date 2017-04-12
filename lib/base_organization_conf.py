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
    def service_url(cls, zone, db_instance_name):
        domain = cls.domain()
        return "{db_instance_name}-postgres.{zone}.{domain}".format(**locals())

    @classmethod
    def server_name(cls, zone, db_instance_name, i):
        domain = cls.domain()
        return "{zone}-postgres-{db_instance_name}-{i}.{zone}.{domain}".format(**locals())

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

