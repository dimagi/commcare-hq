# -*- coding: utf-8 -*-

from django.test import SimpleTestCase

from corehq.apps.userreports.exceptions import InvalidSQLColumnName
from corehq.apps.userreports.sql import get_table_name, get_column_name
from corehq.apps.userreports.util import validate_sql_column_name


class UtilitiesTestCase(SimpleTestCase):

    def test_table_name(self):
        self.assertEqual('config_report_domain_table_7a7a33ec', get_table_name('domain', 'table'))

    def test_table_trickery(self):
        tricky_one = get_table_name('domain_trick', 'table')
        tricky_two = get_table_name('domain', 'trick_table')
        self.assertNotEqual(tricky_one, tricky_two)

    def test_column_trickery(self):
        real = get_column_name("its/a/trap")
        trap1 = get_column_name("its/a_trap")
        trap2 = get_column_name("its_a/trap")
        trap3 = get_column_name("its_a_trap")
        trap4 = get_column_name("its/a/path/that/also/happens/to/be/a/bunch/longer/than/sixty/three/characters")
        trap4_expected = 'ppens_to_be_a_bunch_longer_than_sixty_three_characters_6174b354'

        self.assertNotEqual(real, trap1)
        self.assertNotEqual(real, trap2)
        self.assertNotEqual(real, trap3)
        self.assertEqual(trap4, trap4_expected)

    def test_sql_column_name_validation(self):
        def _test_is_valid_column_name(test_str):
            self.assertIsNone(validate_sql_column_name(test_str))

        def _test_is_invalid_column_name(test_str):
            self.assertRaises(InvalidSQLColumnName, validate_sql_column_name, test_str)

        _test_is_valid_column_name("a")
        _test_is_valid_column_name("abc")
        _test_is_valid_column_name("abc123")
        _test_is_valid_column_name("_abc123")
        _test_is_valid_column_name("@_abc123")
        _test_is_valid_column_name("#@_abc123")
        _test_is_valid_column_name("#$@_abc123")
        _test_is_valid_column_name("çabc")
        _test_is_valid_column_name("abcç")
        _test_is_valid_column_name(u"çabc")

        _test_is_invalid_column_name('"')
        _test_is_invalid_column_name('a"')
        _test_is_invalid_column_name("'")
        _test_is_invalid_column_name("a'")
        _test_is_invalid_column_name("$")
        _test_is_invalid_column_name("$a")
        _test_is_invalid_column_name("1")
        _test_is_invalid_column_name("1b")
        _test_is_invalid_column_name(u"∫abc")
        _test_is_invalid_column_name(u"abc∫")
