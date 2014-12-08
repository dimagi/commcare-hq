from couchdbkit.ext.django.loading import get_db
from django.test import TestCase
from couchexport.models import ExportSchema, SavedExportSchema
from datetime import datetime, timedelta
from couchexport.util import SerializableFunction
from dimagi.utils.couch.database import get_safe_write_kwargs
import json
from couchexport.models import Format


class ExportSchemaTest(TestCase):

    def testSaveAndLoad(self):
        index = ["foo", 2]
        schema = ExportSchema(index=index, timestamp=datetime.now())
        inner = {"dict": {"bar": 1, "baz": [2,3]},
                 "list": ["foo", "bar"],
                 "dictlist": [{"bip": 1, "bop": "blah"},
                              {"bip": 2, "bop": "blah2"}],
                 "item": "yoyoyo"}
        schema.schema = inner
        schema.save()
        back = ExportSchema.get(schema.get_id)
        self.assertEqual(inner, back.schema)
        self.assertEqual(index, back.index)

    def testGetLast(self):
        indices = ["a string", ["a", "list"]]
        save_args = get_safe_write_kwargs()

        for index in indices:
            self.assertEqual(None, ExportSchema.last(index))
            dt = datetime.utcnow()
            schema1 = ExportSchema(index=index, timestamp=dt)
            schema1.save(**save_args)
            self.assertEqual(schema1._id, ExportSchema.last(index)._id)
            schema2 = ExportSchema(index=index, timestamp=dt + timedelta(seconds=1))
            schema2.save(**save_args)
            self.assertEqual(schema2._id, ExportSchema.last(index)._id)
            schema3 = ExportSchema(index=index, timestamp=dt - timedelta(seconds=1))
            schema3.save(**save_args)
            self.assertEqual(schema2._id, ExportSchema.last(index)._id)


class CustomExportSchema(SavedExportSchema):
    @property
    def filter(self):
        return SerializableFunction()


class SavedSchemaTest(TestCase):
    def setUp(self):
        self.db = get_db('couchexport')
        self.custom_export = CustomExportSchema.wrap({
            'type': 'demo',
            'default_format': Format.JSON,
            'index': json.dumps(['test_custom']),
            'tables': [{
                'index': '#',
                'display': 'Export',
                'columns': [
                    {'index': 'multi', 'display': 'Split', 'doc_type': 'SplitColumn', 'options': ['a', 'b', 'c', 'd']}
                ],
            }]
        })

    def tearDown(self):
        for doc in self.db.all_docs():
            if not doc['id'].startswith('_design'):
                self.db.delete_doc(doc['id'])

    def post_it(self, split_val):
        self.db.save_doc({
                '#export_tag': 'tag',
                'tag': 'test_custom',
                'multi': split_val
            },
            **get_safe_write_kwargs()
        )

    def _test_split_column(self, split_val, row):
        self.post_it(split_val)
        files = self.custom_export.get_export_files()
        data = json.loads(files.file.payload)
        self.assertEqual(data['Export']['headers'], [
            'Split (a)', 'Split (b)', 'Split (c)', 'Split (d)', 'Split (other)'
        ])
        self.assertEqual(len(data['Export']['rows']), 1)
        self.assertEqual(data['Export']['rows'][0], row)

    def test_split_column(self):
        self._test_split_column('a b c d', [1, 1, 1, 1, ''])

    def test_split_column_order(self):
        self._test_split_column('c d a', [1, '', 1, 1, ''])

    def test_split_column_empty(self):
        self._test_split_column('', ['', '', '', '', ''])

    def test_split_column_remainder(self):
        self._test_split_column('c b d e f g', ['', 1, 1, 1, 'e f g'])
