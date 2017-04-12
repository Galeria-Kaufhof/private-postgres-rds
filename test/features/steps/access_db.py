#!/usr/bin/env python2
from __future__ import print_function
import logging
import time
import sys
import psycopg2
from behave import *
from contextlib import contextmanager
from cluster_under_test import *
from db_retriable import *

@when('application inserts {number} batches of test data')
def step_insert_test_data(context, number):
    context.dbt.next_batch_number()
    context.dbt.get_record_number()
    context.dbt.insert_continuously(int(number))

@then(u'no new records found')
def step_insert_test_data(context):
    print(sys.path)
    t.assertEqual(0, sys.path)
    t.assertEqual(0, context.dbt.get_record_number())

@then(u'reading from postgres service url should {expected_result}')
def count_records(context, expected_result):
    """@expected_result: fail or work"""
    try:
        con, cur = context.dbt.db.create_connection_with_cursor()
        cur.execute("SELECT count(*) from testdata;")
        context.dbt.found_records = cur.fetchall()[0][0]
        logging.info("Found {} records in the DB.".format(context.dbt.found_records))
        result = 'work'
    except psycopg2.OperationalError as e:
        logging.warning("Can not read from DB: " + str(e))
        result = 'fail'
    t.assertEqual(expected_result, result)

@then(u'last committed batch - {number} - should be visible')
def step_impl(context, number):
    count_records(context, 'work')
    t.assertEqual(context.dbt.records_in_batches(number), context.dbt.found_records)

@then('I run optional CHECKPOINT for faster replication')
def step_impl(context):
    """
    Do not do this in production. Spreading of checkpoint writes through the
    half of the checkpoint interval (default is 5 min.) is to reduce the IO
    load on the master. Read:
    https://www.postgresql.org/docs/9.6/static/app-pgbasebackup.html (`-c fast` switch)
    https://www.postgresql.org/docs/9.6/static/sql-checkpoint.html
    https://www.postgresql.org/docs/9.6/static/wal-configuration.html
    """
    context.dbt.db.execute('CHECKPOINT;')

@when(u'user changes admin password to {password}')
def step_impl(context, password):
    context.dbt.db.execute("ALTER USER admin WITH ENCRYPTED PASSWORD '{}';".format(password))

@then(u'user can access database with password {password}')
def step_impl(context, password):
    db = DbRetriable(host=ClusterUnderTest.service_url,
            dbname="postgres", user="admin", password=password)
    db.execute("select now();", retry=False)

