from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.models import Application
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.cleanup.tasks import permanently_delete_eligible_data
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import create_case, create_form_for_test
from corehq.messaging.scheduling.models import AlertSchedule


class TestPermanentlyDeleteEligibleData(TestCase):
    """
    This serves as a general smoke test. To see specific tests, see:
    - corehq.apps.cleanup.tests.test_utils:TestHardDeleteSQLObjectsBeforeCutoff
    - corehq.apps.cleanup.tests.test_utils:TestHardDeleteCouchDocsBeforeCutoff
    - corehq.form_processor.tests.test_forms.TestHardDeleteFormsBeforeCutoff
    - corehq.form_processor.tests.test_cases.TestHardDeleteCasesBeforeCutoff
    """

    def test_deletes_data(self):
        before_cutoff = datetime(2020, 1, 1, 12, 29)
        form = create_form_for_test(self.domain, deleted_on=before_cutoff)
        case = create_case(self.domain, deleted_on=before_cutoff, save=True)
        alert_schedule = AlertSchedule.objects.create(domain=self.domain, deleted_on=before_cutoff)

        app = Application(domain=self.domain, name='before-cutoff-app')
        app.save()
        sql_app = DeletedCouchDoc.objects.create(doc_id=app._id,
                                                 doc_type="Application",
                                                 deleted_on=before_cutoff)

        permanently_delete_eligible_data()

        with self.assertRaises(XFormNotFound):
            XFormInstance.objects.get_form(form.form_id)

        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case(case.case_id)

        with self.assertRaises(AlertSchedule.DoesNotExist):
            AlertSchedule.objects.get(schedule_id=alert_schedule.schedule_id)

        with self.assertRaises(ResourceNotFound):
            Application.get_db().get(app._id)

        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(id=sql_app.id)

    def test_does_not_delete_data(self):
        form = create_form_for_test(self.domain, deleted_on=self.cutoff)
        case = create_case(self.domain, deleted_on=self.cutoff, save=True)
        alert_schedule = AlertSchedule.objects.create(domain=self.domain, deleted_on=self.cutoff)

        app = Application(domain=self.domain, name='before-cutoff-app')
        app.save()
        sql_app = DeletedCouchDoc.objects.create(doc_id=app._id,
                                                 doc_type="Application",
                                                 deleted_on=self.cutoff)

        permanently_delete_eligible_data()

        self.assertIsNotNone(XFormInstance.objects.get_form(form.form_id))
        self.assertIsNotNone(CommCareCase.objects.get_case(case.case_id))
        self.assertIsNotNone(AlertSchedule.objects.get(schedule_id=alert_schedule.schedule_id))
        self.assertIsNotNone(Application.get_db().get(app._id))
        self.assertIsNotNone(DeletedCouchDoc.objects.get(id=sql_app.id))

    def setUp(self):
        self.domain = 'test_permanently_delete_eligible_data'
        self.cutoff = datetime(2020, 1, 1, 12, 30)
        patcher = patch('corehq.apps.cleanup.tasks.get_cutoff_date_for_data_deletion')
        self.mock_cutoff = patcher.start()
        self.mock_cutoff.return_value = self.cutoff
        self.addCleanup(patcher.stop)
