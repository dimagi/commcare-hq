from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from django.test import TestCase, override_settings

from corehq.apps.userreports.app_manager.helpers import clean_table_name
from corehq.apps.userreports.const import UCR_SQL_BACKEND
from corehq.apps.userreports.exceptions import TableNotFoundWarning, MissingColumnWarning
from corehq.apps.userreports.models import DataSourceConfiguration, InvalidUCRData
from corehq.apps.userreports.util import get_indicator_adapter
from six.moves import range


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
        self.config = get_sample_config()

    def tearDown(self):
        self.config = get_sample_config()
        self._get_adapter().drop_table()

    def _get_adapter(self):
        return get_indicator_adapter(self.config, raise_errors=True)

    def test_raise_error_for_missing_table(self):
        adapter = self._get_adapter()
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
        adapter = self._get_adapter()
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

    def test_non_nullable_column(self):
        self.config.configured_indicators[0]['is_nullable'] = False
        self.config._id = 'docs id'
        adapter = self._get_adapter()
        adapter.build_table()

        doc = {
            "_id": '123',
            "domain": "domain",
            "doc_type": "CommCareCase",
            "name": None
        }
        adapter.best_effort_save(doc)

        invalid = InvalidUCRData.objects.all()
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0].validation_name, 'not_null_violation')
        self.assertEqual(invalid[0].doc_id, '123')


class AdapterBulkSaveTest(TestCase):

    def setUp(self):
        self.domain = 'adapter_bulk_save'
        self.config = get_sample_config(domain=self.domain)
        self.config.save()
        self.adapter = get_indicator_adapter(self.config, raise_errors=True)

    def tearDown(self):
        self.config.delete()
        self.adapter.clear_table()

    def test_bulk_save(self):
        docs = []
        for i in range(10):
            docs.append({
                "_id": str(i),
                "domain": self.domain,
                "doc_type": "CommCareCase",
                "name": 'doc_name_' + str(i)
            })

        self.adapter.build_table()
        self.adapter.bulk_save(docs)
        self.assertEqual(self.adapter.get_query_object().count(), 10)

        self.adapter.bulk_delete([doc['_id'] for doc in docs])
        self.assertEqual(self.adapter.get_query_object().count(), 0)

    def test_save_rows_empty(self):
        self.adapter.build_table()
        self.adapter.save_rows([])
