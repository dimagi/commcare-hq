from __future__ import absolute_import
from datetime import date
from mock import patch, MagicMock
from django.test import TestCase, override_settings
from casexml.apps.case.mock import CaseStructure
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from ..tasks import EpisodeVoucherUpdate, EpisodeUpdater
from .utils import ENikshayCaseStructureMixin, get_voucher_case_structure
import six


@patch('corehq.apps.callcenter.data_source.call_center_data_source_configuration_provider', MagicMock())
@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestVoucherCounts(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(TestVoucherCounts, self).setUp()
        self.cases = self.create_case_structure()

    def make_voucher(self, prescription, final_prescription_num_days=5,
                     date_fulfilled='2016-08-15', prescription_num_days=10,
                     state="fulfilled", date_issued='2016-08-12'):
        return self.create_voucher_case(
            prescription.case_id, {
                'final_prescription_num_days': final_prescription_num_days,
                'date_fulfilled': date_fulfilled,
                'date_issued': date_issued,
                'state': state,
                'prescription_num_days': prescription_num_days,
            }
        )

    def approve_voucher(self, voucher):
        self.factory.create_or_update_case(CaseStructure(
            case_id=voucher.case_id,
            attrs={
                "create": False,
                "update": {'state': 'approved'}
            },
        ))

    def test_basic_voucher_update(self):
        prescription1 = self.create_prescription_case()
        self.make_voucher(prescription1, 12, date(2017, 1, 1))
        self.make_voucher(prescription1, 7, date(2017, 1, 3))
        prescription2 = self.create_prescription_case()
        self.make_voucher(prescription2, 16, date(2017, 1, 2))
        self.make_voucher(prescription2, 10, date(2017, 1, 4))
        self.assertEqual(
            EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_total_days(),
            {
                "prescription_total_days": 12 + 7 + 16 + 10,
                "prescription_total_days_threshold_30": '2017-01-03',
            }
        )

    def test_thresholds(self):
        prescription = self.create_prescription_case()
        self.make_voucher(prescription, 29, date(2017, 1, 2))
        self.make_voucher(prescription, 1, date(2017, 1, 1))
        # It should hit 30 now, and should flp the order of the above two
        self.make_voucher(prescription, 7, date(2017, 1, 3))
        # This one should trigger both the 60 and 90 thresholds
        voucher = self.make_voucher(prescription, 70, date(2017, 1, 4))
        self.assertEqual(
            EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_total_days(),
            {
                "prescription_total_days": 29 + 1 + 7 + 70,
                "prescription_total_days_threshold_30": '2017-01-02',
                "prescription_total_days_threshold_60": '2017-01-04',
                "prescription_total_days_threshold_90": '2017-01-04',
            }
        )
        self.approve_voucher(voucher)  # approving the voucher shouldn't change anything
        self.assertEqual(
            EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_total_days(),
            {
                "prescription_total_days": 29 + 1 + 7 + 70,
                "prescription_total_days_threshold_30": '2017-01-02',
                "prescription_total_days_threshold_60": '2017-01-04',
                "prescription_total_days_threshold_90": '2017-01-04',
            }
        )

    def test_bets_incentive_threshold(self):
        prescription = self.create_prescription_case()
        self.make_voucher(prescription, 150, date(2017, 1, 1))
        # This voucher should be the one to meet the threshold
        self.make_voucher(prescription, 40, date(2017, 1, 2))
        # This one is over the threshold anyways
        self.make_voucher(prescription, 50, date(2017, 1, 3))
        update = EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_total_days()
        self.assertEqual(
            update['bets_date_prescription_threshold_met'],
            '2017-01-02'
        )

    @patch('custom.enikshay.tasks.AdherenceDatastore', MagicMock())
    def test_case_updates(self):
        with patch('custom.enikshay.tasks.EpisodeAdherenceUpdate.update_json', MagicMock()) as adherence_update:
            adherence_update.return_value = {'update': {}}

            prescription = self.create_prescription_case()
            voucher = self.make_voucher(prescription, 29, date(2017, 1, 2))
            self.make_voucher(prescription, 11, date(2017, 1, 1))

            # the updater should pickup the above changes
            EpisodeUpdater(self.domain).run()

            episode = CaseAccessors(self.domain).get_case(self.cases['episode'].case_id)
            self.assertEqual(episode.get_case_property("prescription_total_days"), six.text_type(29 + 11))

            # test that a subsequent update performs a noop
            self.assertEqual(
                EpisodeVoucherUpdate(self.domain, episode).update_json(),
                {}
            )
            # Updating after a voucher has been approved also shouldn't change anything
            self.approve_voucher(voucher)
            self.assertEqual(
                EpisodeVoucherUpdate(self.domain, episode).update_json(),
                {}
            )

    def test_prescription_refill_due_dates(self):
        prescription = self.create_prescription_case()
        self.make_voucher(
            prescription,
            state="fulfilled",
            final_prescription_num_days=15,
            date_issued='2013-01-01'
        )
        self.make_voucher(
            prescription,
            state="available",
            final_prescription_num_days=15,
            date_issued='2012-12-31'
        )
        self.make_voucher(
            prescription,
            state="rejected",
            final_prescription_num_days=15,
            date_issued='2012-01-02'
        )

        self.assertDictEqual(
            {
                'date_last_refill': '2013-01-01',
                'voucher_length': '15',
                'refill_due_date': '2013-01-16',
            },
            EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_refill_due_dates()
        )

    def test_prescription_refill_due_dates_errors(self):
        prescription = self.create_prescription_case()
        self.make_voucher(
            prescription,
            state="fulfilled",
            final_prescription_num_days='abc',
            date_issued='2013-01-01'
        )
        self.assertDictEqual(
            {},
            EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_refill_due_dates()
        )

        self.make_voucher(
            prescription,
            state="fulfilled",
            final_prescription_num_days=15,
            date_issued='hello'
        )
        self.assertDictEqual(
            {},
            EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_refill_due_dates()
        )

    def test_prescription_refill_missing_days(self):
        prescription = self.create_prescription_case()
        voucher_structure = get_voucher_case_structure(None, prescription.case_id, {
            'date_fulfilled': '2013-01-01',
            'date_issued': '2013-01-01',
            'state': "fulfilled",
        })
        voucher_structure.attrs['update'].pop('final_prescription_num_days', None)
        voucher_structure.attrs['update'].pop('prescription_num_days', None)
        self.factory.create_or_update_case(voucher_structure)
        self.assertDictEqual(
            {},
            EpisodeVoucherUpdate(self.domain, self.cases['episode']).get_prescription_refill_due_dates()
        )

    def test_voucher_generation_dates(self):
        prescription1 = self.create_prescription_case(
            extra_update={
                'drugs_ordered_readable': "Happy Pills, Sad Pills, Buggy Pillz",
            },
        )
        voucher11 = get_voucher_case_structure(None, prescription1.case_id, {
            'date_issued': '2012-01-01',
            'state': "available",
        })
        voucher21 = get_voucher_case_structure(None, prescription1.case_id, {
            'date_issued': '2012-01-01',
            'state': "available",
        })
        prescription2 = self.create_prescription_case(
            extra_update={
                'drugs_ordered_readable': "Other pillz",
            },
        )
        voucher21 = get_voucher_case_structure(None, prescription2.case_id, {
            'date_fulfilled': '2014-01-02',
            'date_issued': '2014-01-01',
            'state': "fulfilled",
        })
        self.factory.create_or_update_cases([voucher11, voucher21])

        self.assertDictEqual(
            {
                'first_voucher_generation_date': u'2012-01-01',
                'first_voucher_drugs': u"Happy Pills, Sad Pills, Buggy Pillz",
                'first_voucher_validation_date': u'2014-01-02',
            },
            EpisodeVoucherUpdate(self.domain, self.cases[self.episode_id]).get_first_voucher_details()
        )
