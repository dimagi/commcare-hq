from django.test import SimpleTestCase
from corehq.apps.userreports.sql import get_table_name


class UtilitiesTestCase(SimpleTestCase):

    def test_table_name(self):
        self.assertEqual('config_report_domain_table_7a7a33ec', get_table_name('domain', 'table'))

    def test_trickery(self):
        tricky_one = get_table_name('domain_trick', 'table')
        tricky_two = get_table_name('domain', 'trick_table')
        self.assertNotEqual(tricky_one, tricky_two)
