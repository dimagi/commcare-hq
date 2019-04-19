from __future__ import absolute_import
from __future__ import unicode_literals


from django.test.testcases import TestCase
from custom.icds_reports.models.aggregate import DailyAttendance, AggregateChildHealthDailyFeedingForms


class TestDailyAttendance(TestCase):

    def test_invalid_forms(self):
        """
        Tests whether the invalid Daily attendance feeding forms are ingored or not.
        To pass this test Code should not include the daily feeding form which does not satisfy the
        filter (awc_open_count=1 OR awc_not_open = 1).
        """
        valid_forms_considered = len(DailyAttendance.objects.filter(awc_id='a14', pse_date='2017-05-28').all())
        self.assertTrue(valid_forms_considered == 0)

    def test_valid_forms(self):
        """
        Tests whether the valid Daily attendance feeding forms are considered   or not.
        To pass this test Code should  include the daily feeding form which does satisfy the
        filter (awc_open_count=1 OR awc_not_open = 1).
        """
        valid_forms_considered = DailyAttendance.objects.filter(awc_id='a14', pse_date='2017-05-21').all()
        self.assertTrue(len(valid_forms_considered) == 1)

        self.assertTrue(valid_forms_considered[0].doc_id == 'test_attendence_2')

    def test_attendence_ignored(self):
        """
        To pass this test the code should not include the cases for which invalid daily feeding form is submitted.
        """
        valid_children_attendance = AggregateChildHealthDailyFeedingForms.objects.filter(case_id='dummy_test_child_case',
                                                                                         month='2017-05-01').all()

        #if the invalid attendance entry removed
        self.assertTrue(len(valid_children_attendance) == 1)
        self.assertTrue(valid_children_attendance[0].case_id == 'dummy_test_child_case')

