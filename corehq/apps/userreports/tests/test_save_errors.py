import uuid

from django.test import TestCase

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.exceptions import (
    MissingColumnWarning,
    TableNotFoundWarning,
)
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    InvalidUCRData,
)
from corehq.apps.userreports.util import get_indicator_adapter


def get_sample_config(domain=None):
    return DataSourceConfiguration(
        domain=domain or 'domain',
        display_name='foo',
        referenced_doc_type='CommCareCase',
        table_id=clean_table_name('domain', str(uuid.uuid4().hex)),
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


class SaveErrorsTest(TestCase):

    def setUp(self):
        super().setUp()
        self.config = get_sample_config()
        self.adapter = get_indicator_adapter(self.config, raise_errors=True)

    def test_raise_error_for_missing_table(self):
        doc = {
            "_id": '123',
            "domain": "domain",
            "doc_type": "CommCareCase",
            "name": 'bob'
        }
        with self.assertRaises(TableNotFoundWarning):
            self.adapter.best_effort_save(doc)

    def test_missing_column(self):
        self.adapter.build_table()
        self.addCleanup(self.adapter.drop_table)

        with self.adapter.engine.begin() as connection:
            context = MigrationContext.configure(connection)
            op = Operations(context)
            op.drop_column(self.adapter.get_table().name, 'name')

        doc = {
            "_id": '123',
            "domain": "domain",
            "doc_type": "CommCareCase",
            "name": 'bob'
        }
        with self.assertRaises(MissingColumnWarning):
            self.adapter.best_effort_save(doc)

    def test_non_nullable_column(self):
        self.config.configured_indicators[0]['is_nullable'] = False
        self.config._id = 'docs id'
        self.adapter.build_table()
        self.addCleanup(self.adapter.drop_table)

        doc = {
            "_id": '123',
            "domain": "domain",
            "doc_type": "CommCareCase",
            "name": None
        }
        self.adapter.best_effort_save(doc)

        invalid = InvalidUCRData.objects.all()
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0].validation_name, 'not_null_violation')
        self.assertEqual(invalid[0].doc_id, '123')


class AdapterBulkSaveTest(TestCase):

    def setUp(self):
        self.domain = 'adapter_bulk_save'
        self.config = get_sample_config(domain=self.domain)
        self.config.save()
        self.addCleanup(self.config.delete)
        self.adapter = get_indicator_adapter(self.config, raise_errors=True)
        self.adapter.build_table()
        self.addCleanup(self.adapter.drop_table)

    def test_bulk_save_and_bulk_delete(self):
        docs = []
        for i in range(10):
            docs.append({
                "_id": str(i),
                "domain": self.domain,
                "doc_type": "CommCareCase",
                "name": 'doc_name_' + str(i)
            })

        self.adapter.bulk_save(docs)
        self.assertEqual(self.adapter.get_query_object().count(), 10)

        self.adapter.bulk_delete(docs)
        self.assertEqual(self.adapter.get_query_object().count(), 0)

    def test_save_rows_accepts_empty_list(self):
        self.adapter.save_rows([])
