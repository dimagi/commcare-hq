import os
import re
from django.conf import settings
from django.test import TestCase
from corehq.apps.app_manager.tests import TestXmlMixin
from corehq.apps.domain.models import Domain
from custom.openclinica.management.commands.odm_to_app import Command


class OdmToAppTest(TestCase, TestXmlMixin):
    root = os.path.join(settings.BASE_DIR, 'custom', 'openclinica', 'tests')
    file_path = ('data', )

    def assertXmlEqual(self, expected, actual, normalize=True):
        def fake_xform_xmlns(xml):
            fake_xmlns = 'http://openrosa.org/formdesigner/deadbeef-cafe-c0de-fade-baseba11babe'
            return re.sub(r'http://openrosa\.org/formdesigner/[\w-]{36}', fake_xmlns, xml)
        super(OdmToAppTest, self).assertXmlEqual(
            fake_xform_xmlns(expected),
            fake_xform_xmlns(actual),
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
