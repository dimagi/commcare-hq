from django.test import TestCase
from couchexport.models import ExportSchema
from datetime import datetime, timedelta
from dimagi.utils.couch.database import get_safe_write_kwargs


class ExportSchemaTest(TestCase):

    def testSaveAndLoad(self):
        index = ["foo", 2]
        schema = ExportSchema(seq="5", index=index, timestamp=datetime.now())
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
            # by design, if something has a timestamp it always wins out, even
            # if something has a higher seq

            dt = datetime.utcnow()
            schema1 = ExportSchema(seq="2", index=index, timestamp=dt)
            schema1.save(**save_args)
            self.assertEqual(schema1._id, ExportSchema.last(index)._id)
            schema2 = ExportSchema(seq="1", index=index, timestamp=dt + timedelta(seconds=1))
            schema2.save(**save_args)
            self.assertEqual(schema2._id, ExportSchema.last(index)._id)
            schema3 = ExportSchema(seq="3", index=index, timestamp=dt - timedelta(seconds=1))
            schema3.save(**save_args)
            self.assertEqual(schema2._id, ExportSchema.last(index)._id)
