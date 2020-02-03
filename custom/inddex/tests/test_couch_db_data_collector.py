from unittest import TestCase
from unittest.mock import patch, Mock

from corehq.apps.fixtures.models import FixtureDataItem
from custom.inddex.couch_db_data_collector import CouchDbDataCollector


class CouchDbDataCollectorTest(TestCase):

    def setUp(self):
        self.couch_db = CouchDbDataCollector('test-domain', )
        self.couch_db.tables = {'test_table': '0123456'}

    def test_get_data_from_table_with_no_table_name_returns_attribute_error(self):
        self.couch_db.tables['other_test_table'] = '6543210'
        with self.assertRaises(AttributeError):
            self.couch_db.get_data_from_table()

    def test_get_data_from_table_with_bad_table_name_returns_value_error(self):
        with self.assertRaises(ValueError):
            self.couch_db.get_data_from_table(table_name='other_test_table')

    @patch.object(FixtureDataItem, 'by_data_type', return_value=[('test_field', ('test_value',))])
    def test_get_data_from_table_with_no_fields_and_values_returns_all_data(self, mock_by_data_type):
        res = self.couch_db.get_data_from_table()
        self.assertEqual(res, mock_by_data_type.return_value)

    @patch.object(FixtureDataItem, 'by_data_type', return_value=[('test_field', ('test_value',))])
    @patch.object(CouchDbDataCollector, '_is_record_valid', return_value=False)
    def test_get_data_from_table_with_record_not_valid_returns_empty_list(self, mock__is_record_valid,
                                                                          mock_by_data_type):
        res = self.couch_db.get_data_from_table(fields_and_values=(('test_field', ('other_test_value',)),))
        self.assertEqual(res, [])

    @patch.object(FixtureDataItem, 'by_data_type', return_value=[('test_field', ('test_value',))])
    @patch.object(CouchDbDataCollector, '_is_record_valid', return_value=True)
    def test_get_data_from_table_with_record_valid_returns_list_with_record(
        self, mock__is_record_valid, mock_by_data_type
    ):
        res = self.couch_db.get_data_from_table(fields_and_values=(('test_field', ('test_value',)),))
        self.assertEqual(mock_by_data_type.return_value, res)

    def test_get_data_from_table_as_dict_key_field_not_in_fields_and_values(self):
        with self.assertRaises(ValueError):
            self.couch_db.get_data_from_table_as_dict('test_key_field', (('test_field', ('test_value',)),))

    @patch.object(CouchDbDataCollector, 'get_data_from_table', return_value=[Mock(fields={
        'test_key_field': Mock(field_list=[Mock(field_value='test_key_value')]),
        'test_field': Mock(field_list=[Mock(field_value='test_value')])
    })])
    def test_get_data_from_table_as_dict_returns_dict(self, mock_get_data_from_table):
        res = self.couch_db.get_data_from_table_as_dict(
            'test_key_field', (('test_key_field', ('test_key_value',)),)
        )
        self.assertEqual(res, {'test_key_value': {'test_field': 'test_value'}})

    def test_records_data_as_dict_fields_to_filter_none_returns_record_as_dict(self):
        res = self.couch_db.records_data_as_dict(Mock(fields={
            'test_field_1': Mock(field_list=[Mock(field_value='test_value')]),
            'test_field_2': Mock(field_list=[]),
        }))
        self.assertEqual(res, {
            'test_field_1': 'test_value',
            'test_field_2': None,
        })

    def test_records_data_as_dict_fields_to_filter_not_none_returns_fields_as_dict(self):
        res = self.couch_db.records_data_as_dict(Mock(fields={
            'test_field_1': Mock(field_list=[Mock(field_value='test_value')]),
            'test_field_2': Mock(field_list=[]),
        }), fields_to_filter=('test_field_1',))
        self.assertEqual(res, {
            'test_field_1': 'test_value',
        })
