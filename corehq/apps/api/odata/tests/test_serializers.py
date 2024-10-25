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
            ODataCaseSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                    'owner_name': 'owner-name-value',
                    'properties': {},
                }],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{'owner-name-label': 'owner-name-value'}]
        )

    def test_unselected_column_excluded(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                    'owner_name': 'owner-name-value',
                    'properties': {},
                }],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{}]
        )

    def test_missing_value_is_null(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                }],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{'owner-name-label': '---'}]
        )

    def test_non_standard_case_property(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                    'property_1': 'property-1-value',
                }],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{'property-1-label': 'property-1-value'}]
        )

    def test_case_id(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': 'case-id-value',
                }],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{'case-id-label': 'case-id-value'}]
        )

    def test_case_name(self):
        self.assertEqual(
            ODataCaseSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                    'name': 'case-name-value',
                }],
                CaseExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{'case-name-label': 'case-name-value'}]
        )

    def test_next_link_present(self):
        meta = {'next': '?limit=1&offset=1'}
        api_path = '/a/odata-test/api/odata/v1/cases/config_id'
        self.assertEqual(
            ODataCaseSerializer.get_next_url(meta, api_path),
            'http://localhost:8000/a/odata-test/api/odata/v1/cases/config_id?limit=1&offset=1'
        )

    def test_next_link_absent(self):
        meta = {'next': None}
        api_path = '/a/odata-test/api/odata/v1/cases/config_id'
        self.assertEqual(
            ODataCaseSerializer.get_next_url(meta, api_path),
            None
        )


class TestODataFormSerializer(SimpleTestCase):

    def test_selected_column_included(self):
        self.assertEqual(
            ODataFormSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                    'user_id': 'the-user-id',
                }],
                FormExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{'user-id': 'the-user-id'}]
        )

    def test_unselected_column_excluded(self):
        self.assertEqual(
            ODataFormSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                    'user_id': 'the-user-id',
                }],
                FormExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{}]
        )

    def test_missing_value_is_null(self):
        self.assertEqual(
            ODataFormSerializer.serialize_documents_using_config(
                [{
                    'domain': 'test_domain',
                    '_id': '54352-25234',
                }],
                FormExportInstance(
                    tables=[
                        TableConfiguration(
                            selected=True,
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
                ),
                0
            ),
            [{'user-id': '---'}]
        )

    def test_next_link_present(self):
        meta = {'next': '?limit=1&offset=1'}
        api_path = '/a/odata-test/api/odata/v1/forms/config_id'
        self.assertEqual(
            ODataFormSerializer.get_next_url(meta, api_path),
            'http://localhost:8000/a/odata-test/api/odata/v1/forms/config_id?limit=1&offset=1'
        )

    def test_next_link_absent(self):
        meta = {'next': None}
        api_path = '/a/odata-test/api/odata/v1/forms/config_id'
        self.assertEqual(
            ODataFormSerializer.get_next_url(meta, api_path),
            None
        )
