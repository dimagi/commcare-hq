from django.test import SimpleTestCase
from datetime import date, timedelta
from couchexport.deid import deid_date


class DeidTests(SimpleTestCase):
    def test_deidentifies_date(self):
        doc = {
            '_id': '123'
        }
        original_value = date(year=2000, month=10, day=10)
        deident_val = deid_date(original_value.isoformat(), doc)
        difference = original_value - deident_val
        self.assertLessEqual(difference, timedelta(days=32))
        self.assertGreaterEqual(difference, timedelta(days=-31))

    def test_deid_date_returns_none_when_key_is_not_found(self):
        doc = {
        }
        self.assertIsNone(deid_date('2000-10-10', doc=doc, key=None))

    def test_deid_date_returns_none_when_key_value_cannot_be_determined_from_document(self):
        self.assertIsNone(deid_date('2000-10-10', doc='', key=None))

    def test_doc_is_unnecessary_when_key_is_provided(self):
        result = deid_date('2000-10-10', doc='', key='mydate')
        self.assertIsInstance(result, date)
