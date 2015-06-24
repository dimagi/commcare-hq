from collections import namedtuple
from casexml.apps.case.xml import V1
from django.conf import settings
from corehq.apps.users.models import CommCareUser
from dimagi.utils.modules import to_function
import itertools


FixtureProvider = namedtuple('FixtureProvider', 'id func')


class FixtureGenerator(object):
    """
    The generator object, which gets fixtures from your config file that should
    be included when OTA restoring.
    
    See: https://bitbucket.org/javarosa/javarosa/wiki/externalinstances
    
    To use, add the following to your settings.py
    
    FIXTURE_GENERATORS = {
        'group1': [
           ('fixture_id', "myapp.fixturegenerators.gen1"),
           ('fixture_id_prefix', "myapp.fixturegenerators.gen2"),
            ...
        ],
        ...
    }
    
    The values in the file should be paths to functions that 
    implement the following API:
    
    func(user, version, last_sync) --> [list of fixture objects]
    
    The function should return an empty list if there are no fixtures
    """

    def __init__(self):
        def to_provider(provider_id, func_path):
            func = to_function(func_path)
            return FixtureProvider(id=provider_id, func=func) if func else None

        self._generator_providers = {}
        if hasattr(settings, "FIXTURE_GENERATORS"):
            for group, func_tuple in settings.FIXTURE_GENERATORS.items():
                self._generator_providers[group] = filter(None, [
                    to_provider(provider_id, func_path) for provider_id, func_path in func_tuple
                ])

    def _get_fixtures(self, group, fixture_id_or_prefix, user, version, last_sync):
        if version == V1:
            return []  # V1 phones will never use or want fixtures

        if getattr(user, "_hq_user", False):
            user = user._hq_user

        if not isinstance(user, CommCareUser):
            return []

        if group:
            providers = self._generator_providers.get(group, [])
        else:
            providers = itertools.chain(*self._generator_providers.values())

        if fixture_id_or_prefix:
            providers = [provider for provider in providers if provider.id.startswith(fixture_id_or_prefix)]

        return itertools.chain(*[provider.func(user, version, last_sync)
                                 for provider in providers])

    def get_fixture_by_id(self, fixture_id_or_prefix, user, version, last_sync=None):
        """
        Only get fixtures with the specified ID.
        """
        return self._get_fixtures(None, fixture_id_or_prefix, user, version, last_sync)

    def get_fixtures(self, user, version, last_sync=None, group=None):
        """
        Gets all fixtures associated with an OTA restore operation
        """
        return self._get_fixtures(group, None, user, version, last_sync)


generator = FixtureGenerator()
