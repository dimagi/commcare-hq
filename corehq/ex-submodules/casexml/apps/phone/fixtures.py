from __future__ import absolute_import  # this package has a module named 'xml'
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod

import six

from xml.etree import cElementTree as ElementTree
from casexml.apps.phone.models import OTARestoreUser
from casexml.apps.case.xml import V1, V2
from django.conf import settings
from dimagi.utils.modules import to_function
import itertools


class FixtureProvider(six.with_metaclass(ABCMeta)):

    @abstractmethod
    def __call__(self, restore_state):
        raise NotImplementedError


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
                self._generator_providers[group] = [_f for _f in [
                    to_function(func_path, failhard=True) for func_path in func_paths
                ] if _f]

    def get_providers(self, user, fixture_id=None, version=V2):
        if version == V1:
            return []  # V1 phones will never use or want fixtures

        if not isinstance(user, OTARestoreUser):
            return []

        providers = list(itertools.chain(*list(self._generator_providers.values())))

        if fixture_id:
            full_id = fixture_id
            prefix = fixture_id.split(':', 1)[0]

            def provider_matches(provider):
                # some providers generate fixtures with dynamic ID's e.g. item-list:my-item-list
                # in which case provider.id is just the prefix.
                return provider.id == full_id or provider.id == prefix

            providers = [provider for provider in providers if provider_matches(provider)]

        return providers

    def _get_fixtures(self, restore_user, fixture_id=None):
        providers = self.get_providers(restore_user, fixture_id=fixture_id)
        restore_state = _get_restore_state(restore_user)
        return itertools.chain(*[
            provider(restore_state)
            for provider in providers
        ])

    def get_fixture_by_id(self, fixture_id, restore_user):
        """
        Only get fixtures with the specified ID.
        """
        fixtures = self._get_fixtures(restore_user, fixture_id)
        for fixture in fixtures:
            if isinstance(fixture, six.binary_type):
                # could be bytes if it's coming from cache
                cached_fixtures = ElementTree.fromstring(
                    b"<cached-fixture>%s</cached-fixture>" % fixture
                )
                for fixture in cached_fixtures:
                    if fixture.attrib.get("id") == fixture_id:
                        return fixture
            elif fixture.attrib.get("id") == fixture_id:
                return fixture


generator = FixtureGenerator()


def _get_restore_state(restore_user):
    from casexml.apps.phone.restore import RestoreState
    from casexml.apps.phone.restore import RestoreParams
    params = RestoreParams(version=V2)
    return RestoreState(
        restore_user.project,
        restore_user,
        params,
        async=False,
        overwrite_cache=False
    )
