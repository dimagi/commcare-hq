import doctest
from unittest.mock import Mock

from django.test import SimpleTestCase

import attr

from corehq.motech.exceptions import ConfigurationError

from .. import bundle
from ..bundle import get_bundle


class GetBundleTest(SimpleTestCase):

    def test_invalid_bundle(self):
        response = Response({'resourceType': 'Bundle', 'entry': 'invalid'})
        requests = Mock()
        requests.get.return_value = response

        with self.assertRaises(ConfigurationError):
            get_bundle(requests, 'Patient/')

    def test_valid_bundle(self):
        valid_bundle = {'resourceType': 'Bundle', 'entry': []}
        response = Response(valid_bundle)
        requests = Mock()
        requests.get.return_value = response

        bundle_ = get_bundle(requests, 'Patient/')
        self.assertEqual(bundle_, valid_bundle)


@attr.s(auto_attribs=True)
class Response:
    data: dict

    def json(self):
        return self.data


def test_doctests():
    results = doctest.testmod(bundle, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
