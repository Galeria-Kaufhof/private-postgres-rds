import sys
from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.lookup import LookupBase

class LookupModule(LookupBase):
    def __init__(self, loader=None, templar=None, **kwargs):
        LookupBase.__init__(self, loader=None, templar=None, **kwargs)

    def lookup_impl(self, *args):
        hostvars = args[0]
        res = {}
        res['slave_upstream'] = 'todo'
        res['postgres-MASTER'] = ['192.168.121.101']
        res['postgres-SLAVES'] = ['192.168.121.102']
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

        """
        ret = []
        return [self.lookup_impl(*terms)]

def testhostvars(server_states):
    # example params: ['EMPTY_DATA_DIR', 'EMPTY_DATA_DIR'])):
    res = {}
    for i, state in enumerate(server_states):
        var = {'ansible_local': {'pg': {'state': state} } }
        res["server{}".format(i+1)] = var
    return res

def lookup(placeholder, *args):
    return testfixture.lookup_impl(*args)

if __name__ == "__main__":
    import doctest
    testfixture = LookupModule()
    sys.exit(doctest.testmod()[0])

