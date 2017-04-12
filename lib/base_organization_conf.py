#!/usr/bin/env python2

class BaseOrganizationConf():
    """
    Contains organization specific naming conventions and urls.
    You can override as many methods as you wish in your own configuration.
    """
    def self.domain():
        return "example.com"

    def self.service_url(zone, db_instance_name):
        domain = self.domain()
        return "{db_instance_name}-postgres.{zone}.{domain}".format(**locals())

    def self.server_name(zone, db_instance_name, i):
        domain = self.domain()
        return "{zone}-postgres-{db_instance_name}-{i}.{zone}.{domain}".format(**locals())
