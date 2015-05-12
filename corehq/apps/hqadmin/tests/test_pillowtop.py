# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Django imports
from django.test import SimpleTestCase

# CCHQ imports
from fab.pillow_settings import apply_pillow_actions_to_pillows, \
    get_pillows_for_env, get_single_pillow_action


class TestPillowTopFiltering(SimpleTestCase):
    """
    Tests the function that excludes certain pillows from running on staging.
    """

    def setUp(self):
        self.pillowtops = {
            'core': [
                'corehq.pillows.case.CasePillow',
                'corehq.pillows.xform.XFormPillow',
                'corehq.pillows.domain.DomainPillow',
                'corehq.pillows.user.UserPillow',
                'corehq.pillows.application.AppPillow',
                'corehq.pillows.group.GroupPillow',
                'corehq.pillows.sms.SMSPillow',
                'corehq.pillows.user.GroupToUserPillow',
                'corehq.pillows.user.UnknownUsersPillow',
                'corehq.pillows.sofabed.FormDataPillow',
                'corehq.pillows.sofabed.CaseDataPillow',
            ],
            'phonelog': [
                'corehq.pillows.log.PhoneLogPillow',
            ],
        }

    def test_no_blacklist_items(self):
        expected_pillows = {u'corehq.pillows.case.CasePillow',
                            u'corehq.pillows.xform.XFormPillow',
                            u'corehq.pillows.domain.DomainPillow',
                            u'corehq.pillows.user.UserPillow',
                            u'corehq.pillows.application.AppPillow',
                            u'corehq.pillows.group.GroupPillow',
                            u'corehq.pillows.sms.SMSPillow',
                            u'corehq.pillows.user.GroupToUserPillow',
                            u'corehq.pillows.user.UnknownUsersPillow',
                            u'corehq.pillows.sofabed.FormDataPillow',
                            u'corehq.pillows.sofabed.CaseDataPillow',
                            u'corehq.pillows.log.PhoneLogPillow'}

        self.assertEqual(expected_pillows, apply_pillow_actions_to_pillows(
            [], self.pillowtops))

    def test_with_blacklist_items(self):
        expected_pillows = {u'corehq.pillows.case.CasePillow',
                            u'corehq.pillows.xform.XFormPillow',
                            u'corehq.pillows.domain.DomainPillow',
                            u'corehq.pillows.user.UserPillow',
                            u'corehq.pillows.application.AppPillow',
                            u'corehq.pillows.group.GroupPillow',
                            u'corehq.pillows.sms.SMSPillow',
                            u'corehq.pillows.user.GroupToUserPillow',
                            u'corehq.pillows.user.UnknownUsersPillow',
                            u'corehq.pillows.sofabed.FormDataPillow',
                            u'corehq.pillows.sofabed.CaseDataPillow'}

        self.assertEqual(expected_pillows, apply_pillow_actions_to_pillows(
            [{'exclude_groups': ['phonelog']}], self.pillowtops))

    def test_loading_existing_conf_file(self):

        expected_action = {'include_groups': ['mvp_indicators']}

        action = get_single_pillow_action('staging')
        self.assertEqual(action.to_json(), expected_action)

    def test_loading_no_existing_conf_file(self):
        action = get_single_pillow_action('foo')
        self.assertIsNone(action)

    def test_india_server_exclusions(self):
        self.pillowtops['fluff'] = [
            'custom.bihar.models.CareBiharFluffPillow',
            'custom.opm.models.OpmCaseFluffPillow',
            'custom.opm.models.OpmUserFluffPillow',
        ]

        pillows = get_pillows_for_env('india', self.pillowtops)
        self.assertNotIn('custom.opm.models.OpmCaseFluffPillow', pillows)
        self.assertNotIn('custom.opm.models.OpmUserFluffPillow', pillows)
        self.assertIn('custom.bihar.models.CareBiharFluffPillow', pillows)
