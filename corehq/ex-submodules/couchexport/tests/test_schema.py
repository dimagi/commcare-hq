from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase, SimpleTestCase
from corehq.util.test_utils import DocTestMixin
from couchexport.export import get_formatted_rows, scalar_never_was
from couchexport.models import ExportSchema
from datetime import datetime, timedelta
from dimagi.utils.couch.database import get_safe_write_kwargs
from six.moves import zip


class ExportSchemaTest(TestCase, DocTestMixin):

    def testSaveAndLoad(self):
        index = ["foo", 2]
        schema = ExportSchema(index=index, timestamp=datetime.utcnow())
        inner = {"dict": {"bar": 1, "baz": [2, 3]},
                 "list": ["foo", "bar"],
                 "dictlist": [{"bip": 1, "bop": "blah"},
                              {"bip": 2, "bop": "blah2"}],
                 "item": "yoyoyo"}
        schema.schema = inner
        schema.save()
        back = ExportSchema.get(schema.get_id)
        self.assertEqual(inner, back.schema)
        self.assertEqual(index, back.index)

    def test_get_last(self):
        indices = ["a string", ["a", "list"]]
        save_args = get_safe_write_kwargs()

        for index in indices:
            self.addCleanup(
                lambda idx: [cp.delete() for cp in ExportSchema.get_all_checkpoints(idx)],
                index
            )

        for index in indices:
            self.assertEqual(None, ExportSchema.last(index))
            dt = datetime.utcnow()
            schema1 = ExportSchema(index=index, timestamp=dt)
            schema1.save(**save_args)
            self.assert_docs_equal(schema1, ExportSchema.last(index))
            schema2 = ExportSchema(index=index, timestamp=dt + timedelta(seconds=1))
            schema2.save(**save_args)
            self.assert_docs_equal(schema2, ExportSchema.last(index))
            schema3 = ExportSchema(index=index, timestamp=dt - timedelta(seconds=1))
            schema3.save(**save_args)
            # still schema2 (which has a later date than schema3)
            self.assert_docs_equal(schema2, ExportSchema.last(index))

    def test_get_all_checkpoints(self):
        index = ["mydomain", "myxmlns"]
        self.addCleanup(lambda: [cp.delete() for cp in ExportSchema.get_all_checkpoints(index)])

        schema1 = ExportSchema(index=index, timestamp=datetime.utcnow())
        schema1.save()
        schema1_prime, = list(ExportSchema.get_all_checkpoints(index))
        self.assert_docs_equal(schema1_prime, schema1)
        schema2 = ExportSchema(index=index, timestamp=datetime.utcnow())
        schema2.save()
        schema1_prime, schema2_prime = list(ExportSchema.get_all_checkpoints(index))
        self.assert_docs_equal(schema1_prime, schema1)
        self.assert_docs_equal(schema2_prime, schema2)


class GetFormattedRowsTests(SimpleTestCase):

    def test(self):
        doc = {
            'gender': 'boy'
        }
        schema = {
            'gender': {
                '': 'string',
                'gender': 'string'
            }
        }
        formatted_rows = get_formatted_rows(doc, schema, '.')
        headers = formatted_rows[0][1][0].get_data()
        values = formatted_rows[0][1][1].get_data()
        row_dict = dict(zip(list(headers), list(values)))
        self.assertEqual(
            row_dict,
            {
                'id': '0',
                'gender.gender': scalar_never_was,
                'gender': 'boy'
            }
        )


class ExportSchemaWrapTest(SimpleTestCase):

    def test_wrap_datetime_hippy(self):
        schema1 = ExportSchema(
            schema={},
            timestamp=datetime(1970, 1, 2),
            index='index',
        )
        schema2 = ExportSchema.wrap(schema1.to_json())
        self.assertEqual(schema2.timestamp, datetime(1970, 1, 2))

    def test_wrap_datetime_min(self):
        schema_bad = ExportSchema(
            schema={},
            timestamp=datetime.min,
            index='index',
        )
        schema_good = ExportSchema.wrap(schema_bad.to_json())
        self.assertEqual(schema_good.timestamp, datetime(1970, 1, 1))
