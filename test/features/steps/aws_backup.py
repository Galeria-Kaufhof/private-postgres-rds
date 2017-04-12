#!/usr/bin/env python2
from __future__ import print_function
from subprocess import call, check_call, check_output, CalledProcessError
from cluster_under_test import *
from datetime import datetime
import boto
import time

def expected_backup_bucket():
    return OrganizationConf.backup_bucket_name(ClusterUnderTest.zone, ClusterUnderTest.db_instance_name)

def run_on_bucket(cmd, suffix=""):
    full_cmd = ". {cred}; aws s3 {cmd} {bucket} {suffix}".format(
        cred=ClusterUnderTest.backup_configurer_aws_credentials,
        cmd=cmd, bucket=expected_backup_bucket(), suffix=suffix)
    print(full_cmd)
    return check_output(full_cmd, shell=True)

def wait_for_s3_consistency():
    time.sleep(3) # Is there a better way, than just to wait?

@given(u'empty backup bucket')
def empty_bucket(context):
    try:
        backup_files = run_on_bucket("ls").splitlines()
    except CalledProcessError as ex: # likely due to NoSuchBucket
        print("Note: ignoring, if there is no backup bucket",  ex)
        return
    run_on_bucket("rm", "--recursive")
    wait_for_s3_consistency()
    backup_files = run_on_bucket("ls").splitlines()
    print(backup_files)
    print('-----')
    # t.assertEqual(0, len(backup_files))

@then(u'backup bucket should exist with new files')
def step_impl(context):
    backup_files = run_on_bucket("ls", "--recursive | grep 'basebackup.tar'").splitlines()
    for line in backup_files:
        print(line)
    t.assertEqual(1, len(backup_files))

