from django.test import TestCase

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.sms.management.commands.backfill_sms_subevent_date import update_subevent_date_from_emails
from corehq.apps.sms.models import MessagingSubEvent
from corehq.apps.sms.tests.data_generator import make_email_event_for_test
from corehq.apps.users.models import CommCareUser


class TestBackfillSubeventDateEmail(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.domain = Domain.get_or_create_with_name("backfill-test", is_active=True)
        cls.addClassCleanup(Subscription._get_active_subscription_by_domain.clear, Subscription, cls.domain.name)
        cls.addClassCleanup(cls.domain.delete)
        user_ids = []
        for i in range(2):
            user = CommCareUser.create(
                cls.domain.name, f"user {i}", "123", None, None, email=f"user{i}@email.com"
            )
            user_ids.append(user.get_id)
            cls.addClassCleanup(user.delete, cls.domain.name, deleted_by=None)

        for i in range(2):
            make_email_event_for_test(cls.domain.name, "test broadcast", user_ids)

        MessagingSubEvent.objects.all().update(date_last_activity=None)

    def test_update_date_last_activity(self):
        self.assertEqual(4, MessagingSubEvent.objects.filter(date_last_activity=None).count())
        rows_updated, iterations = update_subevent_date_from_emails(chunk_size=2)
        self.assertEqual(4, rows_updated)
        self.assertEqual(3, iterations)  # 2 with updates + 1 with no updates
        self.assertFalse(MessagingSubEvent.objects.filter(date_last_activity=None).exists())
