from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from django.test.utils import override_settings

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.tests.app_factory import AppFactory

from corehq.apps.app_manager.views.phone import get_app_list_xml


class ListAppsTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data', 'list_apps')

    def setUp(self):
        super(ListAppsTest, self).setUp()

        self.domains = ['rohan', 'angmar', 'mordor']
        self.factories = [AppFactory(domain, build_version='2.9.0') for domain in self.domains]
        for factory in self.factories:
            factory.new_basic_module('register', 'orc')
            factory.app._id = 'app_id'  # force an ID so we don't have to save the apps

    @override_settings(BASE_ADDRESS='onering.com')
    @override_settings(SERVER_ENVIRONMENT='production')
    def test_get_app_list_xml(self):
        self.assertXmlEqual(
            self.get_xml('list_apps'),
            get_app_list_xml([factory.app for factory in self.factories]).serializeDocument()
        )
