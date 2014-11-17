from casexml.apps.case.xml import V1
from django.conf import settings
from dimagi.utils.modules import to_function
import itertools


class FixtureGenerator(object):
    """
    The generator object, which gets fixtures from your config file that should
    be included when OTA restoring.
    
    See: https://bitbucket.org/javarosa/javarosa/wiki/externalinstances
    
    To use, add the following to your settings.py
    
    FIXTURE_GENERATORS = ["myapp.fixturegenerators.gen1",
                          "myapp.fixturegenerators.gen2", ...]
    
    The values in the file should be paths to functions that 
    implement the following API:
    
    func(user, version, last_sync) --> [list of fixture objects]
    
    The function should return an empty list if there are no fixtures
    """

    def __init__(self):
        self._generator_funcs = []
        if hasattr(settings, "FIXTURE_GENERATORS"):
            for func_path in settings.FIXTURE_GENERATORS:
                func = to_function(func_path)
                if func:
                    self._generator_funcs.append(func)

    def get_fixtures(self, user, version, case_sync_op=None, last_sync=None):
        """
        Gets all fixtures associated with an OTA restore operation
        """
        if version == V1: 
            return []  # V1 phones will never use or want fixtures
        return itertools.chain(*[func(user, version, case_sync_op, last_sync)
                                 for func in self._generator_funcs])


generator = FixtureGenerator()
