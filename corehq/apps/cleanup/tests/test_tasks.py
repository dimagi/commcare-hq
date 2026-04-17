import pytest

from datetime import datetime
from time_machine import travel

from django.test import TestCase, override_settings

from corehq.apps.cleanup.tasks import permanently_delete_eligible_data
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import create_form_for_test


class TestPermanentlyDeleteEligibleData(TestCase):
    """
    This serves as a general smoke test. To see specific tests, see:
    - corehq.form_processor.tests.test_forms.TestHardDeleteFormsBeforeCutoff
    """

    def setUp(self):
        self.domain = 'test_permanently_delete_eligible_data'

    @travel('2020-01-10')
    def test_deletes_data(self):
        form = create_form_for_test(self.domain, deleted_on=datetime(2020, 1, 2))

        with override_settings(DATA_RETENTION_WINDOW=7):
            permanently_delete_eligible_data(dry_run=False)

        with pytest.raises(XFormNotFound):
            XFormInstance.objects.get_form(form.form_id)

    @travel('2020-01-10')
    def test_does_not_delete_data(self):
        form = create_form_for_test(self.domain, deleted_on=datetime(2020, 1, 4))

        with override_settings(DATA_RETENTION_WINDOW=7):
            permanently_delete_eligible_data(dry_run=False)

        XFormInstance.objects.get_form(form.form_id)

    @travel('2020-01-10')
    def test_does_not_delete_data_if_in_dry_run_mode(self):
        form = create_form_for_test(self.domain, deleted_on=datetime(2020, 1, 2))

        with override_settings(DATA_RETENTION_WINDOW=7):
            permanently_delete_eligible_data(dry_run=True)

        XFormInstance.objects.get_form(form.form_id)
