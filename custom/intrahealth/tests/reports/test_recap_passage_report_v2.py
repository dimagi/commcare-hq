# coding=utf-8

import datetime

from mock.mock import MagicMock

from custom.intrahealth.tests.utils import YeksiTestCase
from custom.intrahealth.reports import RecapPassageReport2
from dimagi.utils.dates import DateSpan


class TestRecapPassageReport2(YeksiTestCase):

    def test_recap_passage_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'month': '07',
            'year': '2014',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 6, 30))

        recap_passage_report2 = RecapPassageReport2(request=mock, domain='test-pna')

        recap_passage_report2_first = recap_passage_report2.report_context['reports'][0]['report_table']
        headers = recap_passage_report2_first['headers'].as_export_table[0]
        rows = recap_passage_report2_first['rows']
        title = recap_passage_report2_first['title']
        self.assertEqual(
            title,
            'Recap Passage 2014-07-22'
        )
        self.assertEqual(
            headers,
            [
                'Designations', 'Stock apres derniere livraison',
                'Stock disponible et utilisable a la livraison',
                'Livraison', 'Stock Total', 'Precedent', 'Recu hors entrepots mobiles', 'Non Facturable',
                'Facturable', 'Reelle', 'Stock Total', 'PPS Restant', 'Pertes et Adjustement'
            ]
        )
        self.assertEqual(
            rows,
            [
                ['CU', 3, 3, 2, 5, 0, 0, 0, 0, 0, 5, 0, 0],
                ['DIU', 2, 2, 3, 5, 0, 0, 0, 0, 0, 5, 0, 0],
                ['Depo-Provera', 60, 52, 25, 77, 0, 0, 0, 8, 8, 77, -8, 0],
                ['Jadelle', 6, 6, 5, 11, 0, 0, 0, 0, 0, 11, 0, 0],
                ['Microgynon/Lof.', 42, 42, 0, 42, 0, 0, 0, 0, 0, 42, 0, 0],
                ['Microlut/Ovrette', 15, 12, 18, 30, 0, 0, 0, 3, 3, 30, -3, 0],
                ['Preservatif Feminin', 5, 5, 0, 5, 0, 0, 0, 0, 0, 5, 0, 0],
                ['Preservatif Masculin', 100, 100, 0, 100, 0, 0, 0, 0, 0, 100, 0, 0]
            ]
        )

    def test_recap_passage_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'month': '06',
            'year': '2014',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 6, 30))

        recap_passage_report2 = RecapPassageReport2(request=mock, domain='test-pna')

        recap_passage_report2_first = recap_passage_report2.report_context['reports'][0]['report_table']
        headers = recap_passage_report2_first['headers'].as_export_table[0]
        rows = recap_passage_report2_first['rows']
        title = recap_passage_report2_first['title']
        recap_passage_report2_second = recap_passage_report2.report_context['reports'][1]['report_table']
        self.assertEqual(
            title,
            'Recap Passage 2014-06-10'
        )
        self.assertEqual(
            headers,
            [
                'Designations', 'Stock apres derniere livraison',
                'Stock disponible et utilisable a la livraison',
                'Livraison', 'Stock Total', 'Precedent', 'Recu hors entrepots mobiles', 'Non Facturable',
                'Facturable', 'Reelle', 'Stock Total', 'PPS Restant', 'Pertes et Adjustement'
            ]
        )
        self.assertEqual(
            rows,
            [
                ['CU', 12, 12, 0, 12, 0, 0, 0, 0, 0, 12, 0, 0],
                ['Collier', 9, 9, 0, 9, 4, 0, 0, 0, 0, 9, 4, 0],
                ['DIU', 21, 7, 30, 37, 0, 0, 0, 14, 14, 37, -14, 0],
                ['Depo-Provera', 791, 606, 0, 606, 0, 0, 0, 185, 185, 606, -185, 0],
                ['Jadelle', 45, 28, 20, 48, 0, 0, 0, 17, 17, 48, -17, 0],
                ['Microgynon/Lof.', 801, 522, 160, 682, 0, 0, 0, 279, 279, 682, -279, 0],
                ['Microlut/Ovrette', 234, 197, 0, 197, 0, 0, 0, 37, 37, 197, -37, 0],
                ['Preservatif Feminin', 20, 10, 10, 20, 0, 0, 0, 10, 10, 20, -10, 0],
                ['Preservatif Masculin', 279, 258, 100, 358, 68, 0, 21, 0, 21, 358, 47, 0],
            ]
        )
        headers = recap_passage_report2_second['headers'].as_export_table[0]
        rows = recap_passage_report2_second['rows']
        title = recap_passage_report2_second['title']
        self.assertEqual(
            title,
            'Recap Passage 2014-06-11'
        )
        self.assertEqual(
            headers,
            [
                'Designations', 'Stock apres derniere livraison',
                'Stock disponible et utilisable a la livraison',
                'Livraison', 'Stock Total', 'Precedent', 'Recu hors entrepots mobiles', 'Non Facturable',
                'Facturable', 'Reelle', 'Stock Total', 'PPS Restant', 'Pertes et Adjustement'
            ]
        )
        self.assertEqual(
            rows,
            [
                ['CU', 10, 9, 0, 9, 0, 0, 0, 1, 1, 9, -1, 0],
                ['Collier', 6, 6, 0, 6, 0, 0, 0, 0, 0, 6, 0, 0],
                ['DIU', 6, 6, 0, 6, 0, 0, 0, 0, 0, 6, 0, 0],
                ['Depo-Provera', 160, 145, 0, 145, 0, 0, 0, 15, 15, 145, -15, 0],
                ['Jadelle', 13, 13, 0, 13, 0, 0, 0, 0, 0, 13, 0, 0],
                ['Microgynon/Lof.', 189, 156, 0, 156, 0, 0, 0, 33, 33, 156, -33, 0],
                ['Microlut/Ovrette', 100, 88, 18, 106, 0, 0, 0, 12, 12, 106, -12, 0],
                ['Preservatif Feminin', 15, 15, 0, 15, 0, 0, 0, 0, 0, 15, 0, 0],
                ['Preservatif Masculin', 160, 160, 0, 160, 0, 0, 0, 0, 0, 160, 0, 0],
            ]
        )
