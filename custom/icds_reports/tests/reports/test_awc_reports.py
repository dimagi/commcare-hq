# coding=utf-8
from __future__ import absolute_import
from django.test import TestCase

from custom.icds_reports.reports.awc_reports import get_beneficiary_details


class TestAWCReport(TestCase):
    def test_beneficiary_details_recorded_weight_none(self):
        data = get_beneficiary_details(case_id='6b234c5b-883c-4849-9dfd-b1571af8717b', month=(2017, 5, 1))
        self.assertEqual(data['age_in_months'], 69)
        self.assertEqual(data['sex'], 'M')
        self.assertEqual(data['person_name'], 'Name 3342')
        self.assertEqual(data['mother_name'], u'संगीता')

    def test_beneficiary_details_recorded_weight_is_not_none(self):
        data = get_beneficiary_details(case_id='8e226cc6-740f-4146-b017-69d9f6e9651b', month=(2017, 4, 1))
        self.assertEqual(data['age_in_months'], 53)
        self.assertEqual(data['sex'], 'M')
        self.assertEqual(data['person_name'], 'Name 3141')
        self.assertEqual(data['mother_name'], u'शियामु बाई')
        self.assertEqual(filter(lambda r: r['x'] == 53, data['weight'])[0]['y'], 12.6)
        self.assertEqual(filter(lambda r: r['x'] == 53, data['height'])[0]['y'], 96.0)
        self.assertEqual(filter(lambda r: r['x'] == 96.0, data['wfl'])[0]['y'], 12.6)

    def test_beneficiary_details_have_age_in_month_not_have_recorded_height(self):
        data = get_beneficiary_details(case_id='411c4234-8475-415a-9c28-911b85868aa5', month=(2017, 4, 1))
        self.assertEqual(data['age_in_months'], 36)
        self.assertEqual(data['sex'], 'F')
        self.assertEqual(data['person_name'], 'Name 3483')
        self.assertEqual(data['mother_name'], u'रींकीकुँवर')
