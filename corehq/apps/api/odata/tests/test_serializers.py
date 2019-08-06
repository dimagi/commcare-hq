from __future__ import absolute_import, unicode_literals

from django.test import SimpleTestCase

from corehq.apps.api.odata.serializers import (
    ODataCaseSerializer,
    ODataFormSerializer,
)
from corehq.apps.export.models import (
    CaseExportInstance,
    ExportColumn,
    ExportItem,
    FormExportInstance,
    PathNode,
    TableConfiguration,
)


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
