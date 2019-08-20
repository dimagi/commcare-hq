from __future__ import absolute_import  # this package has a module named 'xml'
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod, abstractproperty

import six

from xml.etree import cElementTree as ElementTree
from casexml.apps.phone.models import OTARestoreUser
from casexml.apps.case.xml import V1, V2
from django.conf import settings
from dimagi.utils.modules import to_function
import itertools


class FixtureProvider(six.with_metaclass(ABCMeta)):
    @abstractproperty
    def id(self):
        """ID of the fixture"""
        raise NotImplementedError

    @abstractmethod
    def __call__(self, restore_state):
        raise NotImplementedError


class FixtureGenerator(object):
    """
    The generator object, which gets fixtures from your config file that should
    be included when OTA restoring.

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

    def __init__(self):
        functions = [to_function(func_path, failhard=True) for func_path in settings.FIXTURE_GENERATORS]
        self._generator_providers = [f for f in functions if f]

    def get_providers(self, user, fixture_id=None, version=V2):
        if version == V1:
            return []  # V1 phones will never use or want fixtures

        if not isinstance(user, OTARestoreUser):
            return []

        return self._generator_providers


generator = FixtureGenerator()
