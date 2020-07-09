import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.sms.models import (
    OUTGOING,
    SMS,
    MessagingEvent,
    MessagingSubEvent,
)
from corehq.messaging.scheduling.models import CommCareUser, SMSContent
from corehq.util.metrics.tests.utils import capture_metrics
from custom.icds.tasks.sms import delete_sms_events


class TestDeleteMessageEvents(DomainSubscriptionMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDeleteMessageEvents, cls).setUpClass()
        cls.domain = uuid.uuid4().hex

        cls.mobile_user = CommCareUser.create(cls.domain, 'mobile', 'abc', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.mobile_user.delete()
        super(TestDeleteMessageEvents, cls).tearDownClass()

    def tearDown(self):
        SMS.objects.filter(domain=self.domain).delete()
        MessagingSubEvent.objects.filter(parent__domain=self.domain).delete()
        MessagingEvent.objects.filter(domain=self.domain).delete()

    def test_prune_message_events(self):
        now = datetime.utcnow()
        self._create_models(now - timedelta(minutes=1))
        self._create_models(now)

        self.assertEqual(20, SMS.objects.all().count())
        self.assertEqual(20, MessagingSubEvent.objects.all().count())
        self.assertEqual(2, MessagingEvent.objects.all().count())

        start = now - timedelta(seconds=1)
        end = now + timedelta(seconds=1)

        with capture_metrics() as metrics:
            delete_sms_events(start, end)

        self.assertEqual(1, metrics.sum('commcare.sms_events.deleted', type='event'))
        self.assertEqual(10, metrics.sum('commcare.sms_events.deleted', type='sub_event'))

        self.assertEqual(20, SMS.objects.all().count())
        self.assertEqual(10, SMS.objects.filter(messaging_subevent_id__isnull=False).count())
        self.assertEqual(10, MessagingSubEvent.objects.all().count())
        self.assertEqual(1, MessagingEvent.objects.all().count())

    def _create_models(self, event_date):
        event = MessagingEvent.objects.create(
            domain=self.domain,
            date=event_date,
            source=MessagingEvent.SOURCE_OTHER,
            source_id='other',
            content_type=MessagingEvent.CONTENT_SMS,
            app_id=None,
            form_unique_id=None,
            form_name=None,
            status=MessagingEvent.STATUS_IN_PROGRESS,
            recipient_type=MessagingEvent.RECIPIENT_UNKNOWN,
            recipient_id=None
        )
        for _ in range(10):
            subevent = event.create_subevent_from_contact_and_content(
                self.mobile_user,
                SMSContent(message={'en': 'Hello'}),
                None
            )
            SMS.objects.create(
                domain=self.domain,
                phone_number="12345",
                direction=OUTGOING,
                date=datetime.utcnow(),
                backend_id=None,
                location_id=None,
                text="test",
                messaging_subevent=subevent
            )
