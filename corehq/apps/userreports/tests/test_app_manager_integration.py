from __future__ import absolute_import
from __future__ import unicode_literals
from copy import copy
from datetime import datetime

from django.test import TestCase
from mock import patch

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.export.dbaccessors import delete_all_export_data_schemas
from corehq.apps.export.system_properties import MAIN_CASE_TABLE_PROPERTIES
from corehq.apps.userreports.app_manager.helpers import get_case_data_sources, get_form_data_sources
from corehq.apps.userreports.reports.builder import DEFAULT_CASE_PROPERTY_DATATYPES
from corehq.apps.userreports.tests.utils import get_simple_xform


class AppManagerDataSourceConfigTest(TestCase):
    domain = 'userreports_test'
    case_type = 'app_data_case'
    parent_type = 'app_data_parent'
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
        # create main form that defines case schema
        m0, f0 = factory.new_basic_module('Main Module', cls.case_type)
        f0.source = get_simple_xform()
        f0.name = {'en': 'Main Form'}
        factory.form_requires_case(f0, case_type=cls.case_type, update={
            cp: '/data/{}'.format(cp) for cp in cls.case_properties.keys()
        })
        cls.main_form = f0
        # create another module/form to generate a parent case relationship
        # for the main case type
        m1, f1 = factory.new_basic_module('Parent Module', cls.parent_type)
        f1.source = get_simple_xform()  # not used, just needs to be some valid XForm
        f1.name = {'en': 'Parent Form'}
        factory.form_opens_case(f1, case_type=cls.parent_type)
        factory.form_opens_case(f1, case_type=cls.case_type, is_subcase=True)
        cls.app = factory.app
        cls.app.save()

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        delete_all_export_data_schemas()
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
        index_column_id = 'indices.app_data_parent'
        app = self.app
        data_sources = get_case_data_sources(app)
        self.assertEqual(2, len(data_sources))
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
                "closed", "closed_by_user_id", "owner_id", "name", "state", "external_id", "count",
            ] +
            list(self.case_properties.keys())
            + [index_column_id]
        )
        self.assertEqual(expected_columns, set(col_back.id for col_back in data_source.get_columns()))

        modified_on = datetime(2014, 11, 12, 15, 37, 49)
        opened_on = datetime(2014, 11, 11, 23, 34, 34, 25)
        parent_id = 'fake-parent-id'
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
            indices=[
                CommCareCaseIndex(
                    identifier='parent', referenced_type=self.parent_type, referenced_id=parent_id
                )
            ]
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
            if result.column.id == index_column_id:
                self.assertEqual(parent_id, result.value)
            elif result.column.id == "last_modified_date":
                self.assertEqual(modified_on, result.value)
            elif result.column.id == "opened_date":
                self.assertEqual(opened_on, result.value)
            elif result.column.id == "count":
                self.assertEqual(1, result.value)
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
        self.assertEqual(2, len(data_sources))
        data_source = data_sources[self.main_form.xmlns]
        form_properties = copy(self.case_properties)
        form_properties['state'] = 'string'
        # prepend "form." on all form properties
        form_properties = {'form.{}'.format(k): v for k, v in form_properties.items()}
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
