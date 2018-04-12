from __future__ import absolute_import
from __future__ import unicode_literals
import os
from copy import copy
from datetime import datetime

from django.test import TestCase
from mock import patch

from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.export.system_properties import MAIN_CASE_TABLE_PROPERTIES
from corehq.apps.userreports.app_manager.helpers import get_case_data_sources, get_form_data_sources
from corehq.apps.userreports.reports.builder import DEFAULT_CASE_PROPERTY_DATATYPES


class AppManagerDataSourceConfigTest(TestCase):
    domain = 'userreports_test'
    case_type = 'app_data_case'
    case_properties = {
        'first_name': 'string',
        'last_name': 'string',
        'children': 'integer',
        'dob': 'date',
    }

    @classmethod
    def setUpClass(cls):
        super(AppManagerDataSourceConfigTest, cls).setUpClass()
        factory = AppFactory(domain=cls.domain)
        m0, f0 = factory.new_basic_module('A Module', cls.case_type)
        with open(os.path.join(os.path.dirname(__file__), 'data', 'forms', 'simple.xml')) as f:
            form_source = f.read()
        f0.source = form_source
        cls.form = f0
        factory.form_requires_case(f0, case_type=cls.case_type, update={
            cp: '/data/{}'.format(cp) for cp in cls.case_properties.keys()
        })
        cls.app = factory.app
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        super(AppManagerDataSourceConfigTest, cls).tearDownClass()

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        is_usercase_in_use_mock.return_value = False

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    @patch('corehq.apps.userreports.specs.datetime')
    def test_simple_case_management(self, datetime_mock):
        fake_time_now = datetime(2015, 4, 24, 12, 30, 8, 24886)
        datetime_mock.utcnow.return_value = fake_time_now

        app = self.app
        data_sources = get_case_data_sources(app)
        self.assertEqual(1, len(data_sources))
        data_source = data_sources[self.case_type]
        self.assertEqual(self.domain, data_source.domain)
        self.assertEqual('CommCareCase', data_source.referenced_doc_type)
        self.assertEqual(self.case_type, data_source.table_id)
        self.assertEqual(self.case_type, data_source.display_name)

        # test the filter
        self.assertTrue(data_source.filter(
            {'doc_type': 'CommCareCase', 'domain': self.domain, 'type': self.case_type}))
        self.assertFalse(data_source.filter(
            {'doc_type': 'CommCareCase', 'domain': 'wrong-domain', 'type': self.case_type}))
        self.assertFalse(data_source.filter(
            {'doc_type': 'NotCommCareCase', 'domain': self.domain, 'type': self.case_type}))
        self.assertFalse(data_source.filter(
            {'doc_type': 'CommCareCase', 'domain': self.domain, 'type': 'wrong-type'}))

        # check the indicators
        datetime_columns = ["last_modified_date", "opened_date", "closed_date", "inserted_at",
                            "server_last_modified_date"]
        expected_columns = set(
            datetime_columns +
            [
                "doc_id", "case_type", "last_modified_by_user_id", "opened_by_user_id",
                "closed", "closed_by_user_id", "owner_id", "name", "state", "external_id"
            ] +
            list(self.case_properties.keys())
        )
        self.assertEqual(expected_columns, set(col_back.id for col_back in data_source.get_columns()))

        modified_on = datetime(2014, 11, 12, 15, 37, 49)
        opened_on = datetime(2014, 11, 11, 23, 34, 34, 25)
        sample_doc = CommCareCase(
            _id='some-doc-id',
            modified_on=modified_on,
            opened_on=opened_on,
            user_id="23407238074",
            owner_id="0923409230948",
            name="priority ticket",
            domain=app.domain,
            type=self.case_type,
            first_name='test first',
            last_name='test last',
            children='3',
            dob='2001-01-01',
        ).to_json()


        def _get_column_property(column):
            # this is the mapping of column id to case property path
            property_map = {
                c.label: c.item.path[0].name for c in MAIN_CASE_TABLE_PROPERTIES
            }
            property_map.update({
                'doc_id': '_id',
            })
            return property_map.get(column.id, column.id)

        default_case_property_datatypes = DEFAULT_CASE_PROPERTY_DATATYPES
        [row] = data_source.get_all_values(sample_doc)
        for result in row:
            if result.column.id in datetime_columns:
                self.assertEqual(result.column.datatype, 'datetime')

            if result.column.id == "inserted_at":
                self.assertEqual(fake_time_now, result.value)
            elif result.column.id == "last_modified_date":
                self.assertEqual(modified_on, result.value)
            elif result.column.id == "opened_date":
                self.assertEqual(opened_on, result.value)
            elif result.column.id not in ["repeat_iteration", "inserted_at", 'closed']:
                self.assertEqual(sample_doc[_get_column_property(result.column)], result.value)
                if result.column.id in default_case_property_datatypes:
                    self.assertEqual(
                        result.column.datatype,
                        default_case_property_datatypes[result.column.id]
                    )

    def test_simple_form_data_source(self):
        app = self.app
        data_sources = get_form_data_sources(app)
        self.assertEqual(1, len(data_sources))
        data_source = data_sources[self.form.xmlns]
        form_properties = copy(self.case_properties)
        form_properties['state'] = 'string'
        meta_properties = {
            'username': 'string',
            'userID': 'string',
            'started_time': 'datetime',
            'completed_time': 'datetime',
            'deviceID': 'string',
        }
        for indicator in data_source.configured_indicators:
            if indicator['display_name'] in form_properties:
                datatype = form_properties.pop(indicator['display_name'])
                self.assertEqual(datatype, indicator['datatype'])
            elif indicator['display_name'] in meta_properties:
                datatype = meta_properties.pop(indicator['display_name'])
                self.assertEqual(datatype, indicator['datatype'])

        self.assertEqual({}, form_properties)
        self.assertEqual({}, meta_properties)
