from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from django.test import SimpleTestCase

from corehq.apps.api.odata.serializers import (
    ODataCaseSerializer,
    ODataFormSerializer,
    get_properties_to_include,
    update_case_json,
)
from corehq.apps.export.models import (
    CaseExportInstance,
    ExportColumn,
    ExportItem,
    FormExportInstance,
    PathNode,
    TableConfiguration,
)


class TestDeprecatedODataCaseSerializer(SimpleTestCase):

    def test_update_case_json(self):
        case_json = {
            'date_closed': None,
            'domain': 'test-domain',
            'xform_ids': ['ddee0178-bce1-49cd-bf26-4d5be0fb5a27'],
            'date_modified': '2019-01-23T18:24:33.118000Z',
            'server_date_modified': '2019-01-23T18:24:33.199266Z',
            'id': '50ff9e8b-30de-4a9a-98fd-f997e7b438da',
            'opened_by': '753f34ff0856210e339878e36a0001a5',
            'server_date_opened': '2019-01-23T18:24:33.199266Z',
            'case_id': '50ff9e8b-30de-4a9a-98fd-f997e7b438da',
            'closed': False,
            'indices': {},
            'user_id': '753f34ff0856210e339878e36a0001a5',
            'indexed_on': '2019-04-29T16:03:12.434334',
            'properties': {
                'case_type': 'my_case_type',
                'owner_id': '753f34ff0856210e339878e36a0001a5',
                'external_id': None,
                'case_name': 'nick',
                'date_opened': '2019-01-23T18:24:33.118000Z',
                'included_property': 'abc'
            },
            'resource_uri': ''
        }
        with patch('corehq.apps.api.odata.serializers.get_case_type_to_properties', return_value={
            'my_case_type': ['included_property', 'missing_property']
        }):
            case_properties_to_include = get_properties_to_include('fake_domain', 'my_case_type')
        update_case_json(case_json, case_properties_to_include)
        self.assertEqual(case_json, {
            'date_closed': None,
            'domain': 'test-domain',
            'xform_ids': ['ddee0178-bce1-49cd-bf26-4d5be0fb5a27'],
            'date_modified': '2019-01-23T18:24:33.118000Z',
            'server_date_modified': '2019-01-23T18:24:33.199266Z',
            'opened_by': '753f34ff0856210e339878e36a0001a5',
            'server_date_opened': '2019-01-23T18:24:33.199266Z',
            'case_id': '50ff9e8b-30de-4a9a-98fd-f997e7b438da',
            'closed': False,
            'user_id': '753f34ff0856210e339878e36a0001a5',
            'owner_id': '753f34ff0856210e339878e36a0001a5',
            'case_type': 'my_case_type',
            'case_name': 'nick',
            'date_opened': '2019-01-23T18:24:33.118000Z',
            'included_property': 'abc',
            'missing_property': None,
            'backend_id': None
        })


class TestODataCaseSerializer(SimpleTestCase):

    def test_selected_column_included(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_cases_using_config(
                [{'owner_name': 'owner-name-value', 'properties': {}}],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='owner-name-label',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='owner_name')
                                        ]
                                    ),
                                    selected=True,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{'owner-name-label': 'owner-name-value'}]
        )

    def test_unselected_column_excluded(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_cases_using_config(
                [{'owner_name': 'owner-name-value', 'properties': {}}],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='owner-name-label',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='owner_name')
                                        ]
                                    ),
                                    selected=False,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{}]
        )

    def test_missing_value_is_null(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_cases_using_config(
                [{}],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='owner-name-label',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='owner_name')
                                        ]
                                    ),
                                    selected=True,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{'owner-name-label': '---'}]
        )

    def test_non_standard_case_property(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_cases_using_config(
                [{'property_1': 'property-1-value'}],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='property-1-label',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='property_1')
                                        ]
                                    ),
                                    selected=True,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{'property-1-label': 'property-1-value'}]
        )

    def test_case_id(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_cases_using_config(
                [{'_id': 'case-id-value'}],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='case-id-label',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='_id')
                                        ]
                                    ),
                                    selected=True,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{'case-id-label': 'case-id-value'}]
        )

    def test_case_name(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_cases_using_config(
                [{'name': 'case-name-value'}],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='case-name-label',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='name')
                                        ]
                                    ),
                                    selected=True,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{'case-name-label': 'case-name-value'}]
        )

    def test_next_link_present(self):
        meta = {'next': '?limit=1&offset=1'}
        api_path = '/a/odata-test/api/v0.5/odata/cases/config_id'
        self.assertEqual(
            ODataCaseSerializer.get_next_url(meta, api_path),
            'http://localhost:8000/a/odata-test/api/v0.5/odata/cases/config_id?limit=1&offset=1'
        )

    def test_next_link_absent(self):
        meta = {'next': None}
        api_path = '/a/odata-test/api/v0.5/odata/cases/config_id'
        self.assertEqual(
            ODataCaseSerializer.get_next_url(meta, api_path),
            None
        )


class TestODataFormSerializer(SimpleTestCase):

    def test_selected_column_included(self):
        self.assertEqual(
            ODataFormSerializer.serialize_forms_using_config(
                [{'user_id': 'the-user-id'}],
                FormExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='user-id',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='user_id')
                                        ]
                                    ),
                                    selected=True,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{'user-id': 'the-user-id'}]
        )

    def test_unselected_column_excluded(self):
        self.assertEqual(
            ODataFormSerializer.serialize_forms_using_config(
                [{'user_id': 'the-user-id'}],
                FormExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='user-id',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='user_id')
                                        ]
                                    ),
                                    selected=False,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{}]
        )

    def test_missing_value_is_null(self):
        self.assertEqual(
            ODataFormSerializer.serialize_forms_using_config(
                [{}],
                FormExportInstance(
                    tables=[
                        TableConfiguration(
                            columns=[
                                ExportColumn(
                                    label='user-id',
                                    item=ExportItem(
                                        path=[
                                            PathNode(name='user_id')
                                        ]
                                    ),
                                    selected=True,
                                )
                            ]
                        )
                    ]
                )
            ),
            [{'user-id': '---'}]
        )

    def test_next_link_present(self):
        meta = {'next': '?limit=1&offset=1'}
        api_path = '/a/odata-test/api/v0.5/odata/forms/config_id'
        self.assertEqual(
            ODataFormSerializer.get_next_url(meta, api_path),
            'http://localhost:8000/a/odata-test/api/v0.5/odata/forms/config_id?limit=1&offset=1'
        )

    def test_next_link_absent(self):
        meta = {'next': None}
        api_path = '/a/odata-test/api/v0.5/odata/forms/config_id'
        self.assertEqual(
            ODataFormSerializer.get_next_url(meta, api_path),
            None
        )
