import json
import os
from django.test import SimpleTestCase
from couchforms.models import XFormInstance
from custom.intrahealth.calculations import get_payment_month_from_form, get_case_id_from_form, \
    get_calculated_amount_owed_from_form


class CalculationTestCase(SimpleTestCase):

    def setUp(self):
        with open(os.path.join(os.path.dirname(__file__), 'data', 'operateur_form.json')) as f:
            self.form = XFormInstance.wrap(json.loads(f.read()))

    def test_extract_month(self):
        year, month = get_payment_month_from_form(self.form)
        self.assertEqual(2014, year)
        self.assertEqual(5, month)

    def test_extract_caseid(self):
        self.assertEqual('36f7ab065b274aae95e4da60aa1f6fd2', get_case_id_from_form(self.form))

    def test_extract_amount_owed(self):
        self.assertEqual(6042, get_calculated_amount_owed_from_form(self.form))
