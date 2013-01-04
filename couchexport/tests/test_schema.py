from django.test import TestCase
from couchexport.models import ExportSchema
from datetime import datetime
import time

class ExportSchemaTest(TestCase):

    def testSaveAndLoad(self):
        index = ["foo", 2]
        schema = ExportSchema(seq=5, index=index)
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
        for index in indices:
            self.assertEqual(None, ExportSchema.last(index))
            schema1 = ExportSchema(seq=2, index=index)
            schema1.save()
            self.assertEqual(schema1._id, ExportSchema.last(index)._id)
            schema2 = ExportSchema(seq=3, index=index)
            schema2.save()
            self.assertEqual(schema2._id, ExportSchema.last(index)._id)
            # by design, if something has a timestamp it always wins out, even
            # if something has a higher seq
            schema3 = ExportSchema(seq=1, index=index, timestamp=datetime.utcnow())
            schema3.save()
            self.assertEqual(schema3._id, ExportSchema.last(index)._id)
            time.sleep(.1)
            schema4 = ExportSchema(seq=1, index=index, timestamp=datetime.utcnow())
            schema4.save()
            self.assertEqual(schema4._id, ExportSchema.last(index)._id)
