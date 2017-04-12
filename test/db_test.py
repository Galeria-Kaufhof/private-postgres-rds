from __future__ import print_function
import logging
import time
import sys
import psycopg2
from behave import *
from contextlib import contextmanager
from cluster_under_test import *
from db_retriable import *

class DbTest:
    """
    DB test fixture to fill database with random testdata.

    Features:

    * create table and indices if needed
    * insert data in batches of BATCH_SIZE
    * transactional: either the whole batch is inserted or no records
    * if connection to postgres lost, retry with increasing intervals

    """

    DEFAULT_BATCH_SIZE = 100000
    DEFAULT_LOADTEST_FACTOR = 1

    def __init__(self, behave_userdata, is_loadtest=False):
        """
        Via behave_userdata you can modify the amount of test data globally to both:
        * test performance with big data amounts
        * enable quick feedback and quick smoke test of all functinality

        You can vary both the size and number of batches with test data. Reducing
        the *number* of batches with LOADTEST_FACTOR gives the biggest acceleration.
        Use e.g. ``behave -D BATCH_SIZE=10000 -D LOADTEST_FACTOR=20``

        For behave's userdata documentation see
        http://pythonhosted.org/behave/behave.html?highlight=userdata
        """
        self.batch_size = behave_userdata.getint("BATCH_SIZE") or DbTest.DEFAULT_BATCH_SIZE
        if is_loadtest:
            self.loadtest_factor = behave_userdata.getint("LOADTEST_FACTOR") \
                                   or DbTest.DEFAULT_LOADTEST_FACTOR
        else:
            self.loadtest_factor = 1

        self.batch = 0
        self.db = DbRetriable(host=ClusterUnderTest.service_url,
                dbname="postgres", user="admin", password=ClusterUnderTest.admin_password)

    def batches(self, n):
        "Global adjustment for the number of batches. Reducing for all tests if user desires."
        return int(n) * self.loadtest_factor

    def records_in_batches(self, n):
        """Calculate expected total number of records in given batch number.
        Accounts for global adjustments."""
        return self.batch_size * self.batches(int(n))

    def recreate_tables(self):
        self.db.execute("DROP TABLE IF EXISTS testdata;")
        self.db.execute("CREATE TABLE IF NOT EXISTS testdata(id bigserial primary key, batch integer, try integer, name varchar(100) NOT NULL);")
        self.db.execute("CREATE INDEX IF NOT EXISTS by_batch ON testdata(batch);")

    def insert_continuously(self, nbatches, start_try=1):
        print("Inserting data in batches of {}:  ".format(self.batch_size), end='')
        for i in range(self.batches(nbatches)):
            self.batch += 1
            for (con, cur, ntry) in self.db.run_with_retry():
                cur.execute("""INSERT INTO testdata(batch, try, name)
                  SELECT %s, %s, md5(random()::text)
                  FROM generate_series(1,%s);""",
                  (self.batch, ntry, self.batch_size))
                con.commit()

            sys.stdout.write(str(self.batch) + ", ")
            sys.stdout.flush()

    def get_record_number(self):
        return self.db.execute("SELECT count(*) from testdata;")[0]

    def next_batch_number(self):
        print("Checking the last batch number")
        for (con, cur, ntry) in self.db.run_with_retry():
            cur.execute("SELECT max(batch) from testdata;")
            max_batch = cur.fetchall()[0][0] or 0
            self.batch = (max_batch / 1000 + 1) * 1000 # round up the batch number

