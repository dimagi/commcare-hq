import datetime

from django.test import TestCase

from corehq.util.models import (
    BouncedEmail,
    PermanentBounceMeta,
    BounceSubType,
    BOUNCE_EVENT_THRESHOLD,
    ComplaintBounceMeta,
    TransientBounceEmail,
    LEGACY_BOUNCE_MANAGER_DATE,
)


class TestBouncedEmails(TestCase):
    SUPPRESSED_BOUNCE = 'permanent_bounce@gmail.com'
    UNDETERMINED_BOUNCE = 'undetermined_bounce@gmail.com'
    GENERAL_BOUNCE = 'general_bounce@gmail.com'
    GENERAL_AT_TRESH = 'general_bounce_stillok@gmail.com'
    GENERAL_ABOVE_THRESH = 'general_bounce_bad@gmail.com'
    TRANSIENT_AT_THRESH = 'transient_bounce_stillok@gmail.com'
    EXPIRED_TRANSIENT_AT_THRESH = 'expired_transient@gmail.com'
    TRANSIENT_ABOVE_THRESH = 'transient_bounce_bad@gmail.com'
    COMPLAINT = 'complaint@gmail.com'
    LEGACY_BOUNCE = 'legacy_bounce@gmail.com'

    @staticmethod
    def _create_permanent_meta(email_address, sub_type, num_records=1):
        bounced_email = BouncedEmail.objects.create(email=email_address)
        for rec_num in range(0, num_records):
            PermanentBounceMeta.objects.create(
                bounced_email=bounced_email,
                timestamp=datetime.datetime.utcnow(),
                sub_type=sub_type,
            )

    @staticmethod
    def _create_transient_meta(email_address, num_records=1, timestamp=None):
        for rec_num in range(0, num_records):
            transient_bounce = TransientBounceEmail.objects.create(
                email=email_address,
                timestamp=timestamp or datetime.datetime.utcnow(),
            )
            if timestamp:
                transient_bounce.created = timestamp
                transient_bounce.save()

    def setUp(self):
        super().setUp()
        self._create_permanent_meta(
            self.SUPPRESSED_BOUNCE,
            BounceSubType.SUPPRESSED
        )
        self._create_permanent_meta(
            self.UNDETERMINED_BOUNCE,
            BounceSubType.UNDETERMINED
        )
        self._create_permanent_meta(
            self.GENERAL_BOUNCE,
            BounceSubType.GENERAL
        )
        self._create_permanent_meta(
            self.GENERAL_AT_TRESH,
            BounceSubType.GENERAL,
            BOUNCE_EVENT_THRESHOLD,
        )
        self._create_permanent_meta(
            self.GENERAL_ABOVE_THRESH,
            BounceSubType.GENERAL,
            BOUNCE_EVENT_THRESHOLD + 1,
        )
        self._create_transient_meta(
            self.TRANSIENT_AT_THRESH,
            BOUNCE_EVENT_THRESHOLD,
        )
        self._create_transient_meta(
            self.TRANSIENT_ABOVE_THRESH,
            BOUNCE_EVENT_THRESHOLD + 1,
        )
        self._create_transient_meta(
            self.EXPIRED_TRANSIENT_AT_THRESH,
            BOUNCE_EVENT_THRESHOLD + 1,
            timestamp=datetime.datetime.utcnow() - datetime.timedelta(days=2)
        )
        legacy_email = BouncedEmail.objects.create(
            email=self.LEGACY_BOUNCE,
            created=LEGACY_BOUNCE_MANAGER_DATE - datetime.timedelta(days=1)
        )
        legacy_email.created = LEGACY_BOUNCE_MANAGER_DATE - datetime.timedelta(days=1)
        legacy_email.save()
        complaint_email = BouncedEmail.objects.create(email=self.COMPLAINT)
        ComplaintBounceMeta.objects.create(
            bounced_email=complaint_email,
            timestamp=datetime.datetime.now(),
        )

    def tearDown(self):
        ComplaintBounceMeta.objects.all().delete()
        PermanentBounceMeta.objects.all().delete()
        TransientBounceEmail.objects.all().delete()
        BouncedEmail.objects.all().delete()
        super().tearDown()

    def test_hard_bounce_emails(self):
        recipients = [
            'imok@gmail.com',
            self.SUPPRESSED_BOUNCE,
            self.UNDETERMINED_BOUNCE,
            self.GENERAL_BOUNCE,
            self.GENERAL_AT_TRESH,
            self.GENERAL_ABOVE_THRESH,
            self.TRANSIENT_AT_THRESH,
            self.TRANSIENT_ABOVE_THRESH,
            self.EXPIRED_TRANSIENT_AT_THRESH,
            self.COMPLAINT,
            self.LEGACY_BOUNCE,
        ]

        bounced_emails = BouncedEmail.get_hard_bounced_emails(recipients)
        print(bounced_emails)
        self.assertEqual(
            bounced_emails,
            {
                self.SUPPRESSED_BOUNCE,
                self.UNDETERMINED_BOUNCE,
                self.GENERAL_ABOVE_THRESH,
                self.TRANSIENT_ABOVE_THRESH,
                self.COMPLAINT,
                self.LEGACY_BOUNCE,
            }
        )

    def test_expired_transient_cleanup(self):
        self.assertEqual(
            TransientBounceEmail.get_expired_query().count(),
            BOUNCE_EVENT_THRESHOLD + 1
        )
        TransientBounceEmail.delete_expired_bounces()
        self.assertEqual(
            TransientBounceEmail.get_expired_query().count(),
            0
        )
