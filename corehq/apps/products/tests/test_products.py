from corehq.apps.products.models import Product
from django.test import SimpleTestCase
from jsonobject.exceptions import BadValueError


class WrapProductTest(SimpleTestCase):

    document_class = Product

    def test_yes_z(self):
        date_string = '2014-08-26T15:20:20.062732Z'
        doc = self.document_class.wrap({'last_modified': date_string})
        self.assertEqual(doc.to_json()['last_modified'], date_string)
        date_string_no_usec = '2014-08-26T15:20:20Z'
        date_string_yes_usec = '2014-08-26T15:20:20.000000Z'
        doc = self.document_class.wrap({'last_modified': date_string_no_usec})
        self.assertEqual(doc.to_json()['last_modified'], date_string_yes_usec)

    def test_no_z(self):
        date_string_no_z = '2014-08-26T15:20:20.062732'
        date_string_yes_z = '2014-08-26T15:20:20.062732Z'
        doc = self.document_class.wrap({'last_modified': date_string_no_z})
        self.assertEqual(doc.to_json()['last_modified'], date_string_yes_z)
        # iso_format can, technically, produce this if microseconds
        # happens to be exactly 0
        date_string_no_z = '2014-08-26T15:20:20'
        date_string_yes_z = '2014-08-26T15:20:20.000000Z'
        doc = self.document_class.wrap({'last_modified': date_string_no_z})
        self.assertEqual(doc.to_json()['last_modified'], date_string_yes_z)

    def test_fail(self):
        bad_date_string = '2014-08-26T15:20'
        with self.assertRaises(BadValueError):
            self.document_class.wrap({'last_modified': bad_date_string})
