from abc import ABCMeta, abstractmethod, abstractproperty

from django.conf import settings

from memoized import memoized

from casexml.apps.case.xml import V1
from casexml.apps.phone.models import OTARestoreUser
from dimagi.utils.modules import to_function


class FixtureProvider(metaclass=ABCMeta):
    @abstractproperty
    def id(self):
        """ID of the fixture"""
        raise NotImplementedError

    @abstractmethod
    def __call__(self, restore_state):
        raise NotImplementedError


@memoized
def _fixture_generators():
    """
    See: https://bitbucket.org/javarosa/javarosa/wiki/externalinstances

    To use, add the following to your settings.py

    FIXTURE_GENERATORS = [
       "myapp.fixturegenerators.gen1",
       "myapp.fixturegenerators.gen2",
        ...
    ]

    The values in the file should be paths to objects that
    implement the following API:

    provider(user, version, last_sync) --> [list of fixture objects]
    provider.id --> the ID of the fixture

    If the provider generates multiple fixtures it should use an ID format as follows:
        "prefix:dynamic"
    In this case 'provider.id' should just be the ID prefix.

    The function should return an empty list if there are no fixtures
    """
    functions = [to_function(func_path, failhard=True) for func_path in settings.FIXTURE_GENERATORS]
    return [f for f in functions if f]


def get_fixture_elements(restore_state, timing_context, skip_fixtures):
    if restore_state.version == V1:
        return  # V1 phones will never use or want fixtures

    if not isinstance(restore_state.restore_user, OTARestoreUser):
        return

    for provider in _fixture_generators():
        if not skip_fixtures or getattr(provider, 'ignore_skip_fixtures_flag', False):
            with timing_context('fixture:{}'.format(provider.id)):
                for element in provider(restore_state):
                    yield element
