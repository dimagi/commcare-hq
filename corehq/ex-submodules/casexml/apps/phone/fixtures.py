from casexml.apps.case.xml import V1
from django.conf import settings
from corehq.apps.users.models import CommCareUser
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
        self._generator_funcs = {}
        if hasattr(settings, "FIXTURE_GENERATORS"):
            for group, func_paths in settings.FIXTURE_GENERATORS.items():
                self._generator_funcs[group] = filter(None, [
                    to_function(func_path) for func_path in func_paths
                ])

    def get_fixtures(self, user, version, last_sync=None, group=None):
        """
        Gets all fixtures associated with an OTA restore operation
        """
        if version == V1:
            return []  # V1 phones will never use or want fixtures

        funcs = []
        if getattr(user, "_hq_user", False):
            user = user._hq_user
        if isinstance(user, CommCareUser):
            if group:
                funcs = self._generator_funcs.get(group, [])
            else:
                funcs = itertools.chain(*self._generator_funcs.values())

        return itertools.chain(*[func(user, version, last_sync)
                                 for func in funcs])


generator = FixtureGenerator()
