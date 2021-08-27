import unittest

from django.test import TestCase

from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.commtrack.util import generate_code, make_domain_commtrack, unicode_slug
from corehq.apps.domain.shortcuts import create_domain


class CommtrackUtilsTest(TestCase):

    def test_unicode_slug(self):
        test_cases = (
            ('normal', 'normal'),
            ('unicode', 'unicode'),
            ('    with\n\t  whitespace   ', 'with-whitespace'),
            ('speçial çháracters', 'special-characters'),
            ('हिंदी', 'hindii'),
        )
        for input, output in test_cases:
            self.assertEqual(output, unicode_slug(input))

    def test_make_domain_commtrack(self):
        domain_obj = create_domain("test-make-domain-commtrack")
        make_domain_commtrack(domain_obj)
        self.assertTrue(domain_obj.commtrack_enabled)
        self.assertTrue(domain_obj.locations_enabled)
        config = CommtrackConfig.for_domain(domain_obj.name)
        self.assertEqual(config.to_json(), {
            'domain': 'test-make-domain-commtrack',
            'actions': [{
                'action': 'receipts',
                'subaction': None,
                '_keyword': 'r',
                'caption': 'Received',
            }, {
                'action': 'consumption',
                'subaction': None,
                '_keyword': 'c',
                'caption': 'Consumed',
            }, {
                'action': 'consumption',
                'subaction': 'loss',
                '_keyword': 'l',
                'caption': 'Losses',
            }, {
                'action': 'stockonhand',
                'subaction': None,
                '_keyword': 'soh',
                'caption': 'Stock on hand',
            }, {
                'action': 'stockout',
                'subaction': None,
                '_keyword': 'so',
                'caption': 'Stock-out',
            }],
            'use_auto_emergency_levels': False,
            'sync_consumption_fixtures': False,
            'use_auto_consumption': False,
            'individual_consumption_defaults': False,
            'alert_config': {
                'stock_out_facilities': False,
                'stock_out_commodities': False,
                'stock_out_rates': False,
                'non_report': False,
            },
            'consumption_config': {
                'min_transactions': 2,
                'min_window': 10,
                'optimal_window': None,
                'use_supply_point_type_default_consumption': False,
                'exclude_invalid_periods': False,
            },
            'ota_restore_config': {
                'section_to_consumption_types': {},
                'force_consumption_case_types': [],
                'use_dynamic_product_list': False,
            },
            'stock_levels_config': {
                'emergency_level': 0.5,
                'understock_threshold': 1.5,
                'overstock_threshold': 3,
            }
        })
        config.delete()
        domain_obj.delete()


class GenerateCodeTest(unittest.TestCase):

    def test_no_change_needed(self):
        name = 'turtle'
        existing = []

        self.assertEqual(
            generate_code(name, existing),
            'turtle'
        )

    def test_sluggifies(self):
        name = 'türtłę'
        existing = []

        self.assertEqual(
            generate_code(name, existing),
            'turtle'
        )

    def test_strips_spaces(self):
        name = 'pizza cat'
        existing = []

        self.assertEqual(
            generate_code(name, existing),
            'pizza_cat'
        )

    def test_adds_1(self):
        name = 'turtle'
        existing = ['turtle']

        self.assertEqual(
            generate_code(name, existing),
            'turtle1'
        )

    def test_increments_number(self):
        name = 'taco'
        existing = ['taco', 'taco1', 'taco2', 'taco3']

        self.assertEqual(
            generate_code(name, existing),
            'taco4'
        )

    def test_doesnt_strip_numbers(self):
        name = 'taco1'
        existing = []

        self.assertEqual(
            generate_code(name, existing),
            'taco1'
        )

    def test_doesnt_die_on_only_numbers(self):
        name = '1'
        existing = []

        self.assertEqual(
            generate_code(name, existing),
            '1'
        )

    def test_empty_values(self):
        empty_default = 'no_name'
        self.assertEqual(
            generate_code('', []),
            empty_default,
        )
        self.assertEqual(
            generate_code(None, []),
            empty_default,
        )
