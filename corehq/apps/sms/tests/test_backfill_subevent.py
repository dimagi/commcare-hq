import datetime

from django.test import TestCase

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.sms.management.commands.backfill_sms_subevent_date import (
    update_subevent_date_from_emails,
    update_subevent_date_from_sms,
    update_subevent_date_from_subevent,
    update_subevent_date_from_xform_session,
    update_subevent_domain_from_parent,
)
from corehq.apps.sms.models import MessagingSubEvent
from corehq.apps.sms.tests.data_generator import (
    create_fake_sms,
    make_email_event_for_test,
    make_events_for_test,
    make_survey_sms_for_test,
)
from corehq.apps.users.models import CommCareUser


class TestBackfillSubevent(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.domain = Domain.get_or_create_with_name("backfill-test", is_active=True)
        cls.addClassCleanup(Subscription._get_active_subscription_by_domain.clear, Subscription, cls.domain.name)
        cls.addClassCleanup(cls.domain.delete)

    def test_update_from_email(self):
        self._setup_email_data()
        self._do_backfill_validate_result(update_subevent_date_from_emails)

    def test_update_from_sms(self):
        self._setup_sms_data()
        self._do_backfill_validate_result(update_subevent_date_from_sms)

    def test_update_from_xform_session(self):
        self._setup_survey_data()
        self._do_backfill_validate_result(update_subevent_date_from_xform_session)

    def test_update_from_subevent(self):
        self._setup_subevent_data()
        self._do_backfill_validate_result(update_subevent_date_from_subevent)

    def test_update_subevent_domain(self):
        self._setup_subevent_data_domain()

        rows_updated, iterations = update_subevent_domain_from_parent(chunk_size=2, explain=False)
        self.assertEqual(3, rows_updated)
        self.assertEqual(3, iterations)  # 2 with updates + 1 with no updates
        self.assertFalse(MessagingSubEvent.objects.filter(domain=None).exists())

    def _do_backfill_validate_result(self, update_fn):
        rows_updated, iterations = update_fn(chunk_size=2, explain=False)
        self.assertEqual(3, rows_updated)
        self.assertEqual(3, iterations)  # 2 with updates + 1 with no updates
        self.assertFalse(MessagingSubEvent.objects.filter(date_last_activity=None).exists())

    def _setup_email_data(self):
        user = CommCareUser.create(
            self.domain.name, "user 1", "123", None, None, email="user1@email.com"
        )
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)

        for i in range(4):
            make_email_event_for_test(self.domain.name, "test broadcast", [user.get_id])

        self._reset_dates_and_check()

    def _setup_sms_data(self):
        for i in range(4):
            create_fake_sms(self.domain.name, randomize=True)

        self._reset_dates_and_check()

    def _setup_subevent_data_domain(self):
        for i in range(4):
            create_fake_sms(self.domain.name, randomize=True)

        update_ids = MessagingSubEvent.objects.all()[1:]
        MessagingSubEvent.objects.filter(id__in=update_ids).update(domain=None)
        self.assertEqual(3, MessagingSubEvent.objects.filter(domain=None).count())

    def _setup_survey_data(self):
        for i in range(4):
            make_survey_sms_for_test(self.domain.name, "test survey")

        self._reset_dates_and_check()

    def _setup_subevent_data(self):
        for i in range(4):
            make_events_for_test(self.domain.name, datetime.datetime.utcnow())

        self._reset_dates_and_check()

    def _reset_dates_and_check(self):
        update_ids = MessagingSubEvent.objects.all()[1:]
        MessagingSubEvent.objects.filter(id__in=update_ids).update(date_last_activity=None)
        self.assertEqual(3, MessagingSubEvent.objects.filter(date_last_activity=None).count())
