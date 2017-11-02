from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from django.test import TestCase

from corehq.apps.userreports.app_manager import _clean_table_name
from corehq.apps.userreports.exceptions import TableNotFoundWarning, MissingColumnWarning
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter


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
        adapter = get_indicator_adapter(self.config, raise_errors=True)
        adapter.drop_table()

        doc = {
            "_id": '123',
            "domain": "domain",
            "doc_type": "CommCareCase",
            "name": 'bob'
        }
        with self.assertRaises(TableNotFoundWarning):
            adapter.best_effort_save(doc)

    def test_missing_column(self):
        adapter = get_indicator_adapter(self.config, raise_errors=True)
        adapter.build_table()
        with adapter.engine.begin() as connection:
            context = MigrationContext.configure(connection)
            op = Operations(context)
            op.drop_column(adapter.get_table().name, 'name')

        doc = {
            "_id": '123',
            "domain": "domain",
            "doc_type": "CommCareCase",
            "name": 'bob'
        }
        with self.assertRaises(MissingColumnWarning):
            adapter.best_effort_save(doc)
