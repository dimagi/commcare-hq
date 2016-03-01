import os
import re
from django.conf import settings
from django.test import TestCase
from corehq.apps.app_manager.tests import TestXmlMixin
from corehq.apps.domain.models import Domain
from custom.openclinica.management.commands.odm_to_app import Command


def replace_uuids(string):
    fake_uuid = 'baseba11-babe-d0es-c0de-affab1ec0b01'
    return re.sub(r'(resource id="|http://openrosa\.org/formdesigner/)(?:[a-f0-9-]{36}|[a-f0-9]{32})',
                  r'\1' + fake_uuid, string)


class OdmToAppTest(TestCase, TestXmlMixin):
    root = os.path.join(settings.BASE_DIR, 'custom', 'openclinica', 'tests')
    file_path = ('data', )

    def assertXmlEqual(self, expected, actual, normalize=True):
        super(OdmToAppTest, self).assertXmlEqual(
            replace_uuids(expected),
            replace_uuids(actual),
            normalize
        )

    def setUp(self):
        domain = Domain.get_or_create_with_name('test_domain')
        filename = os.path.join(settings.BASE_DIR, 'custom', 'openclinica', 'tests', 'data', 'test_metadata.xml')
        command = Command()
        command.handle('test_domain', 'test_app', filename)
        self.app = domain.full_applications(include_builds=False)[0]

    def tearDown(self):
        self.app.delete_app()

    def test_odm_to_app_suite(self):
        self.assertXmlEqual(self.get_xml('suite'), self.app.create_suite())

    def test_odm_to_app_xform(self):
        def as_utf8(string):
            return string.encode('utf-8') if isinstance(string, unicode) else string
        expected = self.get_xml('xform')
        actual = self.app.modules[1].forms[0].source
        self.assertXmlEqual(expected, as_utf8(actual))
