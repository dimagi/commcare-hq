# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
import unittest
from corehq.apps.commtrack.util import unicode_slug, generate_code


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
