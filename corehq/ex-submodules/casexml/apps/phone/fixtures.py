from collections import namedtuple
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
    
    FIXTURE_GENERATORS = {
        'group1': [
           "myapp.fixturegenerators.gen1",
           "myapp.fixturegenerators.gen2",
            ...
        ],
        ...
    }
    
    The values in the file should be paths to objects that
    implement the following API:
    
    provider(user, version, last_sync) --> [list of fixture objects]
    provider.id --> the ID of the fixture

    If the provider generates multiple fixtures it should use an ID format as follows:
        "prefix:dynamic"
    In this case 'provider.id' should just be the ID prefix.
    
    The function should return an empty list if there are no fixtures
    """

    def __init__(self):
        self._generator_providers = {}
        if hasattr(settings, "FIXTURE_GENERATORS"):
            for group, func_paths in settings.FIXTURE_GENERATORS.items():
                self._generator_providers[group] = filter(None, [
                    to_function(func_path) for func_path in func_paths
                ])

    def _get_fixtures(self, group, fixture_id, user, version, last_sync):
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

        if fixture_id:
            full_id = fixture_id
            prefix = fixture_id.split(':', 1)[0]

            def provider_matches(provider):
                # some providers generate fixtures with dynamic ID's e.g. item-list:my-item-list
                # in which case provider.id is just the prefix.
                return provider.id == full_id or provider.id == prefix

            providers = [provider for provider in providers if provider_matches(provider)]

        return itertools.chain(*[provider(user, version, last_sync)
                                 for provider in providers])

    def get_fixture_by_id(self, fixture_id, user, version, last_sync=None):
        """
        Only get fixtures with the specified ID.
        """
        fixtures = self._get_fixtures(None, fixture_id, user, version, last_sync)
        for fixture in fixtures:
            if fixture.attrib.get("id") == fixture_id:
                return fixture

    def get_fixtures(self, user, version, last_sync=None, group=None):
        """
        Gets all fixtures associated with an OTA restore operation
        """
        return self._get_fixtures(group, None, user, version, last_sync)


generator = FixtureGenerator()
