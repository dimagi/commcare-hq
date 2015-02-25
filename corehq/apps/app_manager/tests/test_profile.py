# coding: utf-8
from django.test import SimpleTestCase
from corehq.apps.app_manager.commcare_settings import SETTINGS_LOOKUP, SETTINGS
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestFileMixin
import xml.etree.ElementTree as ET

from corehq.apps.builds.models import BuildSpec


class ProfileTest(SimpleTestCase, TestFileMixin):
    file_path = ('data',)

    def setUp(self):
        self.app = Application(build_spec=BuildSpec(
            version='2.7.0'
            ),
            name=u"TÉST ÁPP"
        )

    def _test_profile(self, app):
        profile = app.create_profile()
        assert isinstance(profile, bytes), type(profile)
        assert u"TÉST ÁPP" in profile.decode('utf-8')
        profile_xml = ET.fromstring(profile)
        types = {
            'features': self._test_feature,
            'properties': self._test_property,
        }
        for p_type, test_method in types.items():
            for key, value in app.profile.get(p_type, {}).items():
                setting = SETTINGS_LOOKUP[p_type][key]
                test_method(profile_xml, key, value, setting)

    def _get_node(self, profile, key, xpath_template):
        xpath = xpath_template.format(key)
        node = profile.find(xpath)
        self.assertIsNotNone(node, 'Node not found: {}.'.format(xpath))
        return node

    def _test_feature(self, profile, key, value, setting):
        node = self._get_node(profile, key, './features/{}')
        self.assertEqual(node.get('active'), value, 'Feature "{}"'.format(key))

    def _test_property(self, profile, key, value, setting):
        node = self._get_node(profile, key, "./property[@key='{}']")
        self.assertEqual(node.get('value'), value, 'Property "{}"'.format(key))

        force = setting.get('force', False)
        force_actual = node.get('force')
        if not force:
            self.assertIn(
                force_actual,
                [None, 'false'],
                '"force" incorrect for property "{}"'.format(key)
            )
        else:
            self.assertEqual(
                force_actual,
                'true',
                '"force" incorrect for property "{}"'.format(key)
            )

    def test_profile_properties(self):
        for setting in SETTINGS:
            if setting['id'] == 'users':
                continue
            for value in setting.get('values', []):
                self.app.profile = {
                    setting['type']: {
                        setting['id']: value
                    }
                }
                self._test_profile(self.app)

    def test_version(self):
        profile_xml = ET.fromstring(self.app.create_profile())
        root = profile_xml.find('.')
        self.assertEqual(root.get('requiredMajor'), '2')
        self.assertEqual(root.get('requiredMinor'), '7')