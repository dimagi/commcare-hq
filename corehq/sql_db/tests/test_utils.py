from django.test import SimpleTestCase

from corehq.sql_db.util import create_unique_index_name


class TestCreateUniqueIndexName(SimpleTestCase):

    def test_under_max_length_remains_unchanged(self):
        name = create_unique_index_name('app', 'table', ['field_one'])
        self.assertEqual(name, "app_table_field_one_idx")

    def test_accepts_list_of_fields(self):
        name = create_unique_index_name('a', 't', ['field_one', 'field_two'])
        self.assertEqual(name, "a_t_field_one_field_two_idx")

    def test_exceeds_max_length_is_truncated_with_hash(self):
        name = create_unique_index_name('verbose_app', 'verbose_table', ['field_one'])
        self.assertEqual(30, len(name))
        self.assertRegex(name, "verbose_app_verbo_.{8}_idx")

    def test_raises_error_if_app_unspecified(self):
        with self.assertRaises(AssertionError):
            create_unique_index_name(None, 'verbose_table', ['field_one'])

        with self.assertRaises(AssertionError):
            create_unique_index_name('', 'verbose_table', ['field_one'])

    def test_raises_error_if_table_unspecified(self):
        with self.assertRaises(AssertionError):
            create_unique_index_name('app', None, ['field_one'])

        with self.assertRaises(AssertionError):
            create_unique_index_name('app', '', ['field_one'])

    def test_raises_error_if_fields_unspecified(self):
        with self.assertRaises(AssertionError):
            create_unique_index_name('app', 'table', None)

        with self.assertRaises(AssertionError):
            create_unique_index_name('app', 'table', [])

    def test_raises_error_if_fields_is_not_a_list(self):
        with self.assertRaises(AssertionError):
            create_unique_index_name('app', 'table', 'field_one')
