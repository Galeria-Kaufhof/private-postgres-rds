import logging
import os
import sys
from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.lookup import LookupBase

class LookupModule(LookupBase):
    def __init__(self, loader=None, templar=None, **kwargs):
        LookupBase.__init__(self, loader=None, templar=None, **kwargs)

    def lookup_impl(self, *args):
        hostvars = args[0]
        res = {}
        logging.basicConfig(filename='/tmp/compute_postgres_groups.log', filemode='w', level=logging.INFO)

        def get_pg_var(host, varname, default):
            return hostvars[host].get('ansible_local', {}).get('pg', {}).get(varname, default)

        servers = {}
        for host in hostvars:
            servers[host] = get_pg_var(host, 'state', 'UNKNOWN')
        logging.info("\n\nLookup compute_postgres_groups")
        logging.info("Servers:" + str(servers))

        if len(servers) == 0:
            raise Exception("No servers found with filter '{}'".format(name_filter()))

        def detect(servers, state):
            """Returns a list of server names with desired state"""
            return sorted([name for name, st in servers.iteritems() if st == state])

        if len(detect(servers, 'NOT_REACHABLE')) > 0:
            raise Exception("Some servers not reachable. To avoid any possibility for 'split brain' execution stopped!")
        if len(detect(servers, 'UNKNOWN')) > 0:
            raise Exception("State of some servers could not be detected. To avoid any possibility for 'split brain' execution stopped!")

        candidates_master = detect(servers, 'CONFIGURED_MASTER')
        if len(candidates_master) > 1:
            raise Exception("Danger: multiple configured masters detected: {}".format(candidates_master))
        elif len(candidates_master) == 1:
            master = candidates_master[0]
        else:
            candidates_slave = detect(servers, 'CONFIGURED_SLAVE')
            if len(candidates_slave) >= 1:
                master = candidates_slave[0]
            else:
                candidates_empty = detect(servers, 'EMPTY_DATA_DIR')
                if len(candidates_empty) == 0:
                    raise Exception('No candidates for becoming postgres master found. Servers: {}'.format(servers))
                master = candidates_empty[0]

        slaves = []
        deactivated = []
        for server in servers.keys():
            if servers[server] == 'CONFIGURED_SLAVE' or servers[server] == 'EMPTY_DATA_DIR':
                if server != master:
                    slaves.append(server)
            if servers[server] == 'DEACTIVATED':
                deactivated.append(server)
        slaves.sort()
        deactivated.sort()

        slave_upstream = master

        def get_all_hosts_var(hostvars, name):
            """Get the value of an ansible variable, which is supposedly set to the
            same value accross all hosts. Ensure the value is consistent."""
            vals = [variables.get(name) for variables in hostvars.values()]
            if all(x==vals[0] for x in vals): # also works for empty list
                return vals[0]
            else:
                raise Exception("{} value is inconsistent across hostvars. Must be same for all servers.".format(
                    name))

        # see rolling-cluster-upgrade.txt for details
        enforce_upstream = get_all_hosts_var(hostvars, 'ENFORCE_SLAVE_UPSTREAM')
        if enforce_upstream:
            if not enforce_upstream in servers.keys():
                raise ValueError("Desired ENFORCE_SLAVE_UPSTREAM '{}' is not found in the server list '{}'".format(
                    enforce_upstream, servers.keys()))
            if servers[enforce_upstream] == 'EMPTY_DATA_DIR':
                # on this run only let the new intermediate upstream configure and finish replication,
                # do not provision further slaves now - do it on next run
                slaves = [enforce_upstream]
            else:
                # otherwise let all slaves provision normally
                slave_upstream = enforce_upstream # override
            master = None

        logging.info("Checking, which servers to deactivate")

        # see rolling-cluster-upgrade.txt for details
        deactivate = []
        enforce_master = get_all_hosts_var(hostvars, 'ENFORCE_MASTER')
        if enforce_master:
            if not enforce_master in servers.keys():
                raise ValueError("Desired ENFORCE_MASTER '{}' is not found in the server list '{}'".format(
                    enforce_master, servers.keys()))
            if master != enforce_master:
                deactivate.append(master)
                master = enforce_master
                slave_upstream = enforce_master # override
                if master in slaves:
                    slaves.remove(master)
            for slave in slaves: # detect obsolete slaves with obsolete upstream
                logging.info("  Checking slave: " + slave)
                upstream = get_pg_var(slave, 'upstream', None)
                if not upstream and servers[slave] == 'CONFIGURED_SLAVE':
                    msg = """All *existing* slaves must provide the `upstream` fact
                    so we can decide, if we need to deactivate them.
                    Failed to detect the configured postgres upstream for slave {}""".format(
                        slave)
                    logging.error("    " + msg)
                    raise Exception(msg)
                logging.info("    upstream: {} vs. enforce {}".format(upstream, enforce_master))
                if upstream and upstream != enforce_master:
                    logging.info("    Deactivating slave {}".format(slave))
                    deactivate.append(slave)
            # clean up slave list
            for x in deactivate:
                if x in slaves:
                    slaves.remove(x)

        if (master in deactivated) or (master in deactivate):
            master = None

        res = {}
        res['aws_commands_host'] = ['localhost']
        res['postgres'] = servers.keys()
        if master:
            res['postgres-MASTER'] = [master]
        if slaves:
            res['postgres-SLAVES'] = slaves
        if deactivated:
            res['postgres-DEACTIVATED'] = deactivated
        if deactivate:
            res['postgres-DEACTIVATE'] = deactivate

        res['slave_upstream'] = slave_upstream
        return res

    def run(self, terms, variables=None, **kwargs):
        """Parameters (terms) passed to the lookup call:
        * hostvars, including ansible_local.pg facts

        Example usage inside playbook: "{{ lookup('compute_postgres_groups', hostvars) }}"

        >>> g = lookup('compute_postgres_groups', testhostvars(['EMPTY_DATA_DIR', 'EMPTY_DATA_DIR']))
        >>> g['postgres-MASTER']
        ['server1']
        >>> g['postgres-SLAVES']
        ['server2']

        >>> g = lookup('compute_postgres_groups', testhostvars(['CONFIGURED_MASTER', 'EMPTY_DATA_DIR']))
        >>> g['postgres-MASTER']
        ['server1']
        >>> g['postgres-SLAVES']
        ['server2']

        >>> g = lookup('compute_postgres_groups', testhostvars(['EMPTY_DATA_DIR', 'CONFIGURED_SLAVE']))
        >>> g['postgres-MASTER']
        ['server2']
        >>> g['postgres-SLAVES']
        ['server1']

        >>> g = lookup('compute_postgres_groups', testhostvars(['CONFIGURED_SLAVE', 'CONFIGURED_SLAVE']))
        >>> g['postgres-MASTER']
        ['server1']
        >>> g['postgres-SLAVES']
        ['server2']

        # Detect no state
        >>> g = lookup('compute_postgres_groups', {'server1': {'ENFORCE_SLAVE_UPSTREAM': True}})
        Traceback (most recent call last):
        ...
        Exception: State of some servers could not be detected. To avoid any possibility for 'split brain' execution stopped!

        # Detect unknown states
        >>> g = lookup('compute_postgres_groups', testhostvars(['CONFIGURED_SLAVE', 'UNKNOWN']))
        Traceback (most recent call last):
        ...
        Exception: State of some servers could not be detected. To avoid any possibility for 'split brain' execution stopped!

        # Detect inconsistency in extra vars
        >>> hv = testhostvars(['CONFIGURED_SLAVE', 'EMPTY_DATA_DIR'])
        >>> hv['server1']['ENFORCE_SLAVE_UPSTREAM'] = 'server2'
        >>> hv['server2']['ENFORCE_SLAVE_UPSTREAM'] = 'foobar'
        >>> g = lookup('compute_postgres_groups', hv)
        Traceback (most recent call last):
        ...
        Exception: ENFORCE_SLAVE_UPSTREAM value is inconsistent across hostvars. Must be same for all servers.


        # First phase for rolling replication: prepare server 3 - replicate data from existing master
        >>> g = lookup('compute_postgres_groups', testhostvars(['CONFIGURED_MASTER', 'CONFIGURED_SLAVE', 'EMPTY_DATA_DIR', 'EMPTY_DATA_DIR'], {'ENFORCE_SLAVE_UPSTREAM': 'server3'}))
        >>> g.get('postgres-MASTER', 'No master provisioning on this run')
        'No master provisioning on this run'

        # Wait with provisioning server4, only provision the server3
        >>> g['postgres-SLAVES']
        ['server3']
        >>> g.get('postgres-DEACTIVATE')
        >>> g['slave_upstream']
        'server1'


        # First phase for rolling replication: case, where server 3 already prepared
        >>> g = lookup('compute_postgres_groups', testhostvars(['CONFIGURED_MASTER', 'CONFIGURED_SLAVE', 'CONFIGURED_SLAVE', 'EMPTY_DATA_DIR'], {'ENFORCE_SLAVE_UPSTREAM': 'server3'}))
        >>> g.get('postgres-MASTER', 'No master provisioning on this run')
        'No master provisioning on this run'
        >>> g.get('postgres-SLAVES')
        ['server2', 'server3', 'server4']
        >>> g['slave_upstream']
        'server3'

        # Second phase for rolling replication: promote server 3, create additional replica 4
        >>> hv = testhostvars(['CONFIGURED_MASTER', 'CONFIGURED_SLAVE', 'CONFIGURED_SLAVE', 'EMPTY_DATA_DIR'], {'ENFORCE_MASTER': 'server3'})
        >>> g = lookup('compute_postgres_groups', hv)
        Traceback (most recent call last):
        ...
        Exception: All *existing* slaves must provide the `upstream` fact
                            so we can decide, if we need to deactivate them.
                            Failed to detect the configured postgres upstream for slave server2
        >>> hv['server2']['ansible_local']['pg']['upstream'] = 'server1'
        >>> g = lookup('compute_postgres_groups', hv)
        >>> g.get('postgres-MASTER')
        ['server3']
        >>> g.get('postgres-SLAVES')
        ['server4']
        >>> g.get('postgres-DEACTIVATE')
        ['server1', 'server2']
        >>> g['slave_upstream']
        'server3'
        """
        ret = []
        return [self.lookup_impl(*terms)]

def testhostvars(server_states, extra={}):
    """Helper for tests. Creates a deep ansible hostvars stucture to use in
    the tests. Example usage:
    >>> testhostvars(['EMPTY_DATA_DIR', 'EMPTY_DATA_DIR'])
    {'server1': {'ansible_local': {'pg': {'state': 'EMPTY_DATA_DIR'}}}, 'server2': {'ansible_local': {'pg': {'state': 'EMPTY_DATA_DIR'}}}}
    >>> testhostvars(['EMPTY_DATA_DIR'], {'ENFORCE_SLAVE_UPSTREAM': True})
    {'server1': {'ENFORCE_SLAVE_UPSTREAM': True, 'ansible_local': {'pg': {'state': 'EMPTY_DATA_DIR'}}}}
    """
    res = {}
    for i, state in enumerate(server_states):
        var = {'ansible_local': {'pg': {'state': state} } }
        for k, v in extra.iteritems():
            var[k] = v
        res["server{}".format(i+1)] = var
    return res

def lookup(placeholder, *args):
    return testfixture.lookup_impl(*args)

if __name__ == "__main__":
    import doctest
    testfixture = LookupModule()
    sys.exit(doctest.testmod()[0])

