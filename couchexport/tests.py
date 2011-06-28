from django.test import TestCase
from django.conf import settings
import logging
from couchexport.models import ExportSchema

class ExportSchemaTest(TestCase):
    
    def testSaveAndLoad(self):
        schema = ExportSchema(seq=5)
        inner = {"dict": {"bar": 1, "baz": [2,3]},
                 "list": ["foo", "bar"],
                 "dictlist": [{"bip": 1, "bop": "blah"},
                              {"bip": 2, "bop": "blah2"}],
                 "item": "yoyoyo"}
        schema.schema = inner
        schema.save()
        back = ExportSchema.get(schema.get_id)
        self.assertEqual(inner, back.schema)
        
