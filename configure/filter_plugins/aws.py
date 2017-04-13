#!/usr/bin/env python

import botocore
import boto3

from ansible import errors

# TODO refactor these filters to lookup, because lookup better suits the spirit
# of such data, retrieved from aws

def iam_user_info(name):
    client = boto3.Session().client('iam')
    return client.get_user(UserName=name)['User']

def iam_user_arn(name):
    return iam_user_info(name)['Arn']

class FilterModule(object):
    ''' Ansible core jinja2 filters '''

    def filters(self):
        return {
            'iam_user_info': iam_user_info,
            'iam_user_arn': iam_user_arn,
        }
