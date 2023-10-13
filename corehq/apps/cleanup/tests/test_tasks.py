from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.cleanup.tasks import permanently_delete_eligible_data
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import create_form_for_test


class TestPermanentlyDeleteEligibleData(TestCase):
    """
    This serves as a general smoke test. To see specific tests, see:
    - corehq.form_processor.tests.test_forms.TestHardDeleteFormsBeforeCutoff
    """

    def test_deletes_data(self):
        before_cutoff = datetime(2020, 1, 1, 12, 29)
        form = create_form_for_test(self.domain, deleted_on=before_cutoff)

        permanently_delete_eligible_data(dry_run=False)

        with self.assertRaises(XFormNotFound):
            XFormInstance.objects.get_form(form.form_id)

    def test_does_not_delete_data(self):
        form = create_form_for_test(self.domain, deleted_on=self.cutoff)

        permanently_delete_eligible_data(dry_run=False)

        self.assertIsNotNone(XFormInstance.objects.get_form(form.form_id))

    def test_does_not_delete_data_if_in_dry_run_mode(self):
        before_cutoff = datetime(2020, 1, 1, 12, 29)
        form = create_form_for_test(self.domain, deleted_on=before_cutoff)

        permanently_delete_eligible_data(dry_run=True)

        XFormInstance.objects.get_form(form.form_id)

    def setUp(self):
        self.domain = 'test_permanently_delete_eligible_data'
        self.cutoff = datetime(2020, 1, 1, 12, 30)
        patcher = patch('corehq.apps.cleanup.tasks.get_cutoff_date_for_data_deletion')
        self.mock_cutoff = patcher.start()
        self.mock_cutoff.return_value = self.cutoff
        self.addCleanup(patcher.stop)
