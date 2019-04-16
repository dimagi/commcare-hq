from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.userreports.sql import get_column_name
from corehq.apps.userreports.util import get_table_name, truncate_value, UCR_TABLE_PREFIX


class UtilitiesTestCase(SimpleTestCase):

    def test_truncate_value_left(self):
        value = 'string to truncate'
        truncated = truncate_value(value, max_length=len(value) - 1)
        self.assertEqual(truncated, 'truncate_849f01fd')

    def test_truncate_value_right(self):
        value = 'string to truncate'
        truncated = truncate_value(value, max_length=len(value) - 1, from_left=False)
        self.assertEqual(truncated, 'string t_849f01fd')

    def test_truncate_value_unicode_left(self):
        value = '\u00e8 string to truncate\u00e8'
        truncated = truncate_value(value, max_length=len(value) - 1)
        self.assertEqual(truncated, 'runcate\\xe8_6be7bea3')

    def test_truncate_value_unicode_right(self):
        value = '\u00e8 string to truncate\u00e8'
        truncated = truncate_value(value, max_length=len(value) - 1, from_left=False)
        self.assertEqual(truncated, '\\xe8 string_6be7bea3')

    def test_table_name(self):
        self.assertEqual('{}domain_table_7a7a33ec'.format(UCR_TABLE_PREFIX), get_table_name('domain', 'table'))

    def test_table_name_unicode(self):
        self.assertEqual(
            "{}domain_unicode\\\\xe8_8aece1af".format(UCR_TABLE_PREFIX),
            get_table_name('domain', 'unicode\u00e8')
        )

    def test_table_trickery(self):
        tricky_one = get_table_name('domain_trick', 'table')
        tricky_two = get_table_name('domain', 'trick_table')
        self.assertNotEqual(tricky_one, tricky_two)

    def test_long_table_name(self):
        name = get_table_name('this_is_a_long_domain', 'and_a_long_table_name')
        name_expected = '{}this_is_a_long_domain_and_a_long_tabl_3509038f'.format(UCR_TABLE_PREFIX)
        self.assertEqual(name, name_expected)

    def test_column_unicode(self):
        name = get_column_name("Zouti_pou_travay_t\u00e8")
        name_expected = 'Zouti_pou_travay_t\xe8_488e6086'
        self.assertEqual(name, name_expected)

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

    def test_column_name_suffix(self):
        self.assertEqual(
            get_column_name("its/a/path", suffix="string"),
            "its_a_path_dab095d5_string"
        )

    def test_column_length_with_suffix(self):
        long_path = ("its/a/path/that/also/happens/to/be/a/bunch/longer/than/"
                     "sixty/three/characters")
        column_name = get_column_name(long_path, suffix="decimal")
        self.assertEqual(len(column_name), 63)
        self.assertEqual(
            column_name,
            '_be_a_bunch_longer_than_sixty_three_characters_6174b354_decimal',
        )
