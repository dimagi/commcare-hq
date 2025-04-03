import datetime

from corehq.apps.accounting import tasks
from corehq.apps.accounting.models import FormSubmittingMobileWorkerHistory
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.form_processor.utils.xform import TestFormMetadata
from corehq.util.test_utils import make_es_ready_form


@es_test(requires=[form_adapter], setup_class=True)
class TestCalculateFormSubmittingMobileWorkers(BaseInvoiceTestCase):

    def setUp(self):
        super().setUp()
        num_workers = 5
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_workers)

        self.num_form_submitting_workers = 3
        self.one_day_ago = datetime.date.today() - datetime.timedelta(days=1)
        one_week_ago_dt = datetime.datetime.combine(
            self.one_day_ago - datetime.timedelta(days=6), datetime.time()
        )
        for user in self.domain.all_users()[:self.num_form_submitting_workers]:
            self._submit_form(user, one_week_ago_dt)

    def _submit_form(self, user, received_on):
        form_pair = make_es_ready_form(
            TestFormMetadata(
                domain=self.domain.name,
                user_id=user.user_id,
                received_on=received_on
            )
        )
        form_adapter.index(form_pair.json_form, refresh=True)

    def tearDown(self):
        delete_all_users()
        delete_all_domains()
        return super().tearDown()

    def test_calculate_form_submitting_mobile_workers_in_all_domains(self):
        tasks.calculate_form_submitting_mobile_workers_in_all_domains()
        self.assertEqual(FormSubmittingMobileWorkerHistory.objects.count(), 1)

        worker_history = FormSubmittingMobileWorkerHistory.objects.first()
        self.assertEqual(worker_history.domain, self.domain.name)
        self.assertEqual(worker_history.num_users, self.num_form_submitting_workers)
        self.assertEqual(worker_history.record_date, self.one_day_ago)
