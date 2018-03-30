from __future__ import absolute_import
from __future__ import unicode_literals
import os
from copy import copy
from datetime import datetime

from django.test import TestCase
from mock import patch, Mock
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.userreports.app_manager.helpers import get_case_data_sources, get_form_data_sources
from corehq.apps.userreports.reports.builder import DEFAULT_CASE_PROPERTY_DATATYPES
from dimagi.utils.parsing import json_format_datetime


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
        cls.app = Application.new_app(cls.domain, 'Application Data Source App')
        module = cls.app.add_module(Module.new_module('Untitled Module', None))
        module.case_type = cls.case_type
        with open(os.path.join(os.path.dirname(__file__), 'data', 'forms', 'simple.xml')) as f:
            form_source = f.read()
        cls.form = cls.app.new_form(module.id, "Untitled Form", 'en', form_source)
        AppFactory.form_requires_case(cls.form, case_type=cls.case_type, update={
            cp: '/data/{}'.format(cp) for cp in cls.case_properties.keys()
        })
        cls.app.save()
        cls.app = Application.get(cls.app._id)

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        # for config in DataSourceConfiguration.all():
        #     config.delete()
        # delete_all_report_configs()
        super(AppManagerDataSourceConfigTest, cls).tearDownClass()

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        is_usercase_in_use_mock.return_value = False

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    @patch('corehq.apps.userreports.specs.datetime')
    @patch('corehq.apps.app_manager.app_schemas.case_properties.get_per_type_defaults', Mock(return_value={}))
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
        expected_columns = set(
            ["doc_id", "modified_on", "user_id", "opened_on",
             "owner_id", 'inserted_at', 'name'] + self.case_properties.keys()
        )
        self.assertEqual(expected_columns, set(col_back.id for col_back in data_source.get_columns()))

        modified_on = datetime(2014, 11, 12, 15, 37, 49)
        opened_on = datetime(2014, 11, 11, 23, 34, 34, 25)
        sample_doc = dict(
            _id='some-doc-id',
            doc_type="CommCareCase",
            modified_on=json_format_datetime(modified_on),
            user_id="23407238074",
            opened_on=json_format_datetime(opened_on),
            owner_id="0923409230948",
            name="priority ticket",
            domain=app.domain,
            type=self.case_type,
            first_name='test first',
            last_name='test last',
            children='3',
            dob='2001-01-01',
        )

        def _get_column_property(column):
            return column.id if column.id != 'doc_id' else '_id'

        default_case_property_datatypes = DEFAULT_CASE_PROPERTY_DATATYPES
        [row] = data_source.get_all_values(sample_doc)
        for result in row:
            if result.column.id == "inserted_at":
                self.assertEqual(result.column.datatype, 'datetime')
                self.assertEqual(fake_time_now, result.value)
            elif result.column.id == "modified_on":
                self.assertEqual(result.column.datatype, 'datetime')
                self.assertEqual(modified_on, result.value)
            elif result.column.id == "opened_on":
                self.assertEqual(result.column.datatype, 'datetime')
                self.assertEqual(opened_on, result.value)
            elif result.column.id not in ["repeat_iteration", "inserted_at"]:
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
            'timeStart': 'datetime',
            'timeEnd': 'datetime',
            'deviceID': 'string',
        }
        expected_props = len(form_properties) + len(meta_properties)
        self.assertEqual(expected_props, len(data_source.configured_indicators))
        for indicator in data_source.configured_indicators:
            if indicator['display_name'] in form_properties:
                datatype = form_properties.pop(indicator['display_name'])
            else:
                datatype = meta_properties.pop(indicator['display_name'])
            self.assertEqual(datatype, indicator['datatype'])
