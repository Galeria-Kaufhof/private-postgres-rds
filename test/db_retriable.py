import logging
import psycopg2
import psycopg2.extras
import socket
import sys
import time
from cluster_under_test import *

class DbRetriable:
    """
    Wrapper around psycopg2, which offers convenient retry functionality.

    If connection to postgres is lost during query execution or between
    queries, retry with increasing intervals.

    Low level functionality: create_connection_with_cursor, run_with_fail, run_with_retry
    Here you have access to both connection and cursor objects and can e.g
    run multiple inserts with cursor.execute and the commit them together with connection.commit()

    More convenient `execute`: run query, commit, return the records. Is
    sutable for both: selects and insert/update/delete. Supports auto-retry.

    Usage:

        db = DbRetriable(host="...", dbname="postgres", user="...", password="...")

    """

    def __init__(self, host, **other_connection_args):
        """Saves connection_args so they can be later used for connection retry."""
        self.host = host
        self.other_connection_args = other_connection_args
        self.ntry = 1

    def create_connection_with_cursor(self):
        """@returns tuple with connection and cursor"""

        # Reresolve the host name on every connection
        resolved = ClusterUnderTest.resolve_service_url()
        con = psycopg2.connect(host=resolved, **self.other_connection_args)
        cur = con.cursor()
        return (con, cur)

    def run_with_retry(self):
        '''
        Runs a block until queries succeed.

        Generator provides following to the executed block:

            * psycopg2.connection object
            * psycopg2.cursor object
            * number of retries so far

        Example:

        >>> for (con, cur, ntry) in db.run_with_retry():
        ...     cur.execute("""INSERT INTO testdata(batch, try, name)
        ...       SELECT %s, %s, md5(random()::text)
        ...       FROM generate_series(1,%s);""",
        ...       (self.batch, ntry, self.BATCH_SIZE))
        ...     con.commit()


        '''
        last_exception = ''
        delay = 1
        while True:
            try:
                con, cur = self.create_connection_with_cursor()
                yield con, cur, self.ntry
                con.commit()
                break
            except psycopg2.OperationalError as e:
                self.ntry +=1
                if str(e) == last_exception:
                    sys.stdout.write('+')
                    sys.stdout.flush()
                else:
                    last_exception = str(e)
                    print(e)
                time.sleep(delay)
                delay = delay if delay > 15 else delay*2
        if last_exception != '':
            print()

    def run_with_fail(self):
        """
        Similar API to run_with_retry. but try to connect and run the block only once. Fail on failure.
        """
        con, cur = self.create_connection_with_cursor()
        yield con, cur, self.ntry

    def execute(self, query, params=None, retry=False):
        """
        Shortcut to

        * run query with params
        * with retry if desired and necessary
        * commits at the end
        * return the dataset as array, if any

        Is sutable for both: selects and insert/update/delete

        >>> print(db.execute("SELECT count(*) from testdata;")[0])
        """
        if retry:
            for (con, cur, ntry) in self.run_with_retry():
                cur.execute(query, params)
        else:
            for (con, cur, ntry) in self.run_with_fail():
                cur.execute(query, params)
        try:
            res = cur.fetchall()
        except psycopg2.ProgrammingError as ex:
            res = None # no results to fetch
        con.commit()
        return res

