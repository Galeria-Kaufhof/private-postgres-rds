#!/usr/bin/env python2
from __future__ import print_function
import imp
import os
import sys

"""
Load  organization specific configuration from environment.
In all the python modules use:

    from conf import OrganizationConf
    OrganizationConf.service_url(...

"""

if 'RDS_ORGANIZATION_CONF' not in os.environ:
    print('Please set RDS_ORGANIZATION_CONF environment variable. See "getting started" for more information')
    sys.exit(1)

orga_conf = imp.load_source('', os.environ['RDS_ORGANIZATION_CONF'])
OrganizationConf = orga_conf.OrganizationConf

def get_env(key, reason="for this feature to work."):
    """Get a parameter value from environment variable and report error if value is missing"""
    if key in os.environ:
        return os.environ[key]
    else:
        raise ValueError("You need to provide {} env var {}".format(key, reason))

