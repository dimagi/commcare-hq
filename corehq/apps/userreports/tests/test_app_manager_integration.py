import json
import os
from datetime import datetime
from mock import patch
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.userreports.app_manager import get_case_data_sources, get_form_data_sources
from corehq.apps.userreports.reports.builder import DEFAULT_CASE_PROPERTY_DATATYPES


class AppManagerDataSourceConfigTest(SimpleTestCase):

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        self.is_usercase_in_use_mock.return_value = False

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def get_json(self, name):
        with open(os.path.join(os.path.dirname(__file__), 'data', 'app_manager', name)) as f:
            return json.loads(f.read())

    @patch('corehq.apps.userreports.specs.datetime')
    def test_simple_case_management(self, datetime_mock):
        fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)
        datetime_mock.utcnow.return_value = fake_time_now

        app = Application.wrap(self.get_json('simple_app.json'))
        self.assertEqual('userreports_test', app.domain)
        data_sources = get_case_data_sources(app)
        self.assertEqual(1, len(data_sources))
        data_source = data_sources['ticket']
        self.assertEqual(app.domain, data_source.domain)
        self.assertEqual('CommCareCase', data_source.referenced_doc_type)
        self.assertEqual('ticket', data_source.table_id)
        self.assertEqual('ticket', data_source.display_name)

        # test the filter
        self.assertTrue(data_source.filter(
            {'doc_type': 'CommCareCase', 'domain': app.domain, 'type': 'ticket'}))
        self.assertFalse(data_source.filter(
            {'doc_type': 'CommCareCase', 'domain': 'wrong domain', 'type': 'ticket'}))
        self.assertFalse(data_source.filter(
            {'doc_type': 'NotCommCareCase', 'domain': app.domain, 'type': 'ticket'}))
        self.assertFalse(data_source.filter(
            {'doc_type': 'CommCareCase', 'domain': app.domain, 'type': 'not-ticket'}))

        # check the indicators
        expected_columns = set(
            ["doc_id", "modified_on", "user_id", "opened_on",
             "owner_id", "name", "category", "priority", "starred", "estimate", "inserted_at"]
        )
        self.assertEqual(expected_columns, set(col_back.id for col_back in data_source.get_columns()))

        sample_doc = dict(
            _id='some-doc-id',
            doc_type="CommCareCase",
            modified_on="2014-11-12T15:37:49",
            user_id="23407238074",
            opened_on="2014-11-11T23:34:34",
            owner_id="0923409230948",
            name="priority ticket",
            domain=app.domain,
            type='ticket',
            category='bug',
            priority='4',
            starred='yes',
            estimate='2',
        )

        def _get_column_property(column):
            return column.id if column.id != 'doc_id' else '_id'

        default_case_property_datatypes = DEFAULT_CASE_PROPERTY_DATATYPES
        [row] = data_source.get_all_values(sample_doc)
        for result in row:
            if result.column.id == "inserted_at":
                self.assertEqual(result.column.datatype, 'datetime')
                self.assertEqual(fake_time_now, result.value)
            if result.column.id not in ["repeat_iteration", "inserted_at"]:
                self.assertEqual(sample_doc[_get_column_property(result.column)], result.value)
                if result.column.id in default_case_property_datatypes:
                    self.assertEqual(
                        result.column.datatype,
                        default_case_property_datatypes[result.column.id]
                    )

    def test_simple_form_management(self):
        app = Application.wrap(self.get_json('simple_app.json'))
        self.assertEqual('userreports_test', app.domain)
        data_sources = get_form_data_sources(app)
        self.assertEqual(1, len(data_sources))
        data_source = data_sources['http://openrosa.org/formdesigner/AF6F83BA-09A9-4773-9177-AB51EA6CF802']
        for indicator in data_source.configured_indicators:
            self.assertIsNotNone(indicator)
