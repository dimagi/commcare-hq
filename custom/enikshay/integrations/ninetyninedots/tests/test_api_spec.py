from __future__ import absolute_import

from django.test import SimpleTestCase

from custom.enikshay.integrations.ninetyninedots.api_spec import load_api_spec


class NinetyNineDotsSpecLoaderTest(SimpleTestCase):
    def test_loading_spec(self):
        # if the yaml spec file is unable to be loaded, this will throw an error
        load_api_spec()
