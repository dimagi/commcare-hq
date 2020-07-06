import uuid
import xml.etree.cElementTree as ET

from django.test import SimpleTestCase

import mock

from corehq.apps.app_manager.commcare_settings import (
    get_commcare_settings_lookup,
    get_custom_commcare_settings,
)
from corehq.apps.app_manager.models import Application, BuildProfile
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.builds.models import BuildSpec
from corehq.util.test_utils import flag_enabled


@flag_enabled('CUSTOM_PROPERTIES')
class ProfileTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def setUp(self):
        self.build_profile_id = uuid.uuid4().hex
        self.app = Application(
            build_spec=BuildSpec(version='2.7.2'),
            name="TÉST ÁPP",
            domain="potter",
            langs=['en'],
            build_profiles={self.build_profile_id: BuildProfile(langs=['en'], name='en-profile')}
        )

    def _test_profile(self, app):
        profile = app.create_profile()
        assert isinstance(profile, bytes), type(profile)
        assert "TÉST ÁPP" in profile.decode('utf-8')
        profile_xml = ET.fromstring(profile)
        types = {
            'features': self._test_feature,
            'properties': self._test_property,
        }
        for p_type, test_method in types.items():
            for key, value in app.profile.get(p_type, {}).items():
                setting = get_commcare_settings_lookup()[p_type][key]
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
        actual_value = node.get('value')
        msg = 'Expected "{}" to equal "{}", got "{}"'.format(key, value, actual_value)
        self.assertEqual(actual_value, value, msg)

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

    def _test_custom_property(self, profile, key, value):
        node = self._get_node(profile, key, "./property[@key='{}']")
        self.assertEqual(node.get('value'), value, 'Property "{}"'.format(key))

        force_actual = node.get('force')
        self.assertEqual(
            force_actual,
            'true',
            '"force" should always be true for custom properties"{}"'.format(key)
        )

    def test_profile_properties(self):
        for setting in get_custom_commcare_settings():
            if setting['id'] == 'users':
                continue
            for value in setting.get('values', []):
                self.app.profile = {
                    setting['type']: {
                        setting['id']: value
                    }
                }
                self._test_profile(self.app)

        # custom properties do not rely on SETTINGS so need to be tested separately
        self.app.profile = {
            'custom_properties': {
                'random': 'value'
            }
        }
        profile = self.app.create_profile()
        self._test_profile(self.app)
        self._test_custom_property(ET.fromstring(profile), 'random', 'value')

    def test_heartbeat_url_in_profile(self):
        profile = self.app.create_profile()
        self._test_custom_property(ET.fromstring(profile), 'heartbeat-url', self.app.heartbeat_url())
        profile = self.app.create_profile(build_profile_id=self.build_profile_id)
        self._test_custom_property(ET.fromstring(profile), 'heartbeat-url',
                                   self.app.heartbeat_url(self.build_profile_id))

    def test_version(self):
        profile_xml = ET.fromstring(self.app.create_profile())
        root = profile_xml.find('.')
        self.assertEqual(root.get('requiredMajor'), '2')
        self.assertEqual(root.get('requiredMinor'), '7')
        self.assertEqual(root.get('requiredMinimal'), '2')

    @flag_enabled('MOBILE_RECOVERY_MEASURES')
    def test_mobile_recovery_measure(self):
        profile = self.app.create_profile()
        self._test_property(
            ET.fromstring(profile),
            key='recovery-measures-url',
            value=self.app.recovery_measures_url,
            setting={'force': True},
        )
