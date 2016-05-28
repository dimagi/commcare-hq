# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Django imports
from django.test import SimpleTestCase

# CCHQ imports
from corehq.apps.hqadmin.pillow_settings import (
    apply_pillow_actions_to_pillows,
    get_pillows_for_env,
    get_single_pillow_action,
)


class TestPillowTopFiltering(SimpleTestCase):
    """
    Tests the function that excludes certain pillows from running on staging.
    """

    def setUp(self):
        self.pillowtops = {
            'core': [
                'corehq.pillows.case.CasePillow',
                'corehq.pillows.xform.XFormPillow',
            ],
            'phonelog': [
                'corehq.pillows.log.PhoneLogPillow',
            ],
            'newstyle': [
                {
                    'name': 'FakeConstructedPillowName',
                    'class': 'pillowtop.tests.FakeConstructedPillow',
                    'instance': 'pillowtop.tests.make_fake_constructed_pillow'
                }
            ]
        }

    def test_no_blacklist_items(self):
        expected_pillows = {'CasePillow',
                            'XFormPillow',
                            'PhoneLogPillow',
                            'FakeConstructedPillowName',
                            }

        configs_back = apply_pillow_actions_to_pillows([], self.pillowtops)
        self.assertEqual(expected_pillows, set([c.name for c in configs_back]))

    def test_with_blacklist_items(self):
        expected_pillows = {'CasePillow',
                            'XFormPillow',
                            'FakeConstructedPillowName',
                            }

        configs_back = apply_pillow_actions_to_pillows([{'exclude_groups': ['phonelog']}], self.pillowtops)
        self.assertEqual(expected_pillows, set([c.name for c in configs_back]))

    def test_with_exclusion_by_name(self):
        expected_pillows = {'CasePillow',
                            'XFormPillow',
                            'PhoneLogPillow',
                            }

        configs_back = apply_pillow_actions_to_pillows(
            [{'exclude_pillows': ['FakeConstructedPillowName']}],
            self.pillowtops
        )
        self.assertEqual(expected_pillows, set([c.name for c in configs_back]))

    def test_with_exclusion_by_class(self):
        expected_pillows = {'CasePillow',
                            'XFormPillow',
                            'PhoneLogPillow',
                            }

        configs_back = apply_pillow_actions_to_pillows(
            [{'exclude_pillows': ['pillowtop.tests.FakeConstructedPillow']}],
            self.pillowtops
        )
        self.assertEqual(expected_pillows, set([c.name for c in configs_back]))

    def test_loading_existing_conf_file(self):
        config = {'include_groups': ['mvp_indicators']}

        action = get_single_pillow_action(config)
        self.assertEqual(action.to_json(), config)

    def test_india_server_exclusions(self):
        self.pillowtops['fluff'] = [
            'custom.bihar.models.CareBiharFluffPillow',
            'custom.opm.models.OpmUserFluffPillow',
        ]
        configs = [
            {'exclude_groups': ['mvp_indicators', 'fluff']},
            {'include_pillows': ['custom.bihar.models.CareBiharFluffPillow']},
        ]

        pillows = [c.name for c in get_pillows_for_env(configs, self.pillowtops)]
        self.assertNotIn('OpmUserFluffPillow', pillows)
        self.assertIn('CareBiharFluffPillow', pillows)
