import sys
from os import path

# print("====== environment.py extends sys.path ======")
sys.path.insert(0, path.abspath(path.join(__file__, '../..')))
sys.path.insert(0, path.abspath(path.join(__file__, '../../../lib')))
# print('\n'.join(sys.path))
# print('=============================================')

from db_test import *

def before_scenario(context, scenario):
    is_loadtest = 'loadtest' in context.tags
    context.dbt = DbTest(context.config.userdata, is_loadtest=is_loadtest)
    context.extra_inventory_params = '' # always reset extra inventory params


