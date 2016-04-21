import datetime
import uuid

from django.test import TestCase

from corehq.apps.userreports.app_manager import _clean_table_name
from corehq.apps.userreports.exceptions import TableNotFoundWarning
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.sql import ErrorRaisingIndicatorSqlAdapter


class SaveErrorsTest(TestCase):
    def setUp(self):
        self.config = DataSourceConfiguration(
            domain='domain',
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id=_clean_table_name('domain', str(uuid.uuid4().hex)),
            configured_indicators=[{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": 'name'
                },
                "column_id": 'name',
                "display_name": 'name',
                "datatype": "string"
            }],
        )

    def test_raise_error_for_missing_table(self):
        adapter = ErrorRaisingIndicatorSqlAdapter(self.config)
        adapter.drop_table()

        doc = {
            "_id": '123',
            "domain": "domain",
            "doc_type": "CommCareCase",
            "name": 'bob'
        }
        with self.assertRaises(TableNotFoundWarning):
            adapter.best_effort_save(doc)
