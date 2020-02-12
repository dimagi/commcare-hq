import datetime

from django.test import TestCase

from corehq.util.models import (
    BouncedEmail,
    PermanentBounceMeta,
    BounceSubType,
    GENERAL_BOUNCE_THRESHOLD,
    ComplaintBounceMeta,
)


class TestBouncedEmails(TestCase):
    SUPPRESSED_BOUNCE = 'permanent_bounce@gmail.com'
    UNDETERMINED_BOUNCE = 'undetermined_bounce@gmail.com'
    GENERAL_BOUNCE = 'general_bounce@gmail.com'
    GENERAL_AT_TRESH = 'general_bounce_stillok@gmail.com'
    GENERAL_ABOVE_THRESH = 'general_bounce_bad@gmail.com'
    COMPLAINT = 'complaint@gmail.com'
    NO_META_BOUNCE = 'no_meta@gmail.com'

    @staticmethod
    def _create_permanent_meta(email_address, sub_type, num_records=1):
        bounced_email = BouncedEmail.objects.create(email=email_address)
        for rec_num in range(0, num_records):
            PermanentBounceMeta.objects.create(
                bounced_email=bounced_email,
                timestamp=datetime.datetime.now(),
                sub_type=sub_type,
            )

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
            GENERAL_BOUNCE_THRESHOLD,
        )
        self._create_permanent_meta(
            self.GENERAL_ABOVE_THRESH,
            BounceSubType.GENERAL,
            GENERAL_BOUNCE_THRESHOLD + 1,
        )
        BouncedEmail.objects.create(email=self.NO_META_BOUNCE)
        complaint_email = BouncedEmail.objects.create(email=self.COMPLAINT)
        ComplaintBounceMeta.objects.create(
            bounced_email=complaint_email,
            timestamp=datetime.datetime.now(),
        )

    def tearDown(self):
        ComplaintBounceMeta.objects.all().delete()
        PermanentBounceMeta.objects.all().delete()
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
            self.COMPLAINT,
            self.NO_META_BOUNCE,
        ]

        bounced_emails = BouncedEmail.get_hard_bounced_emails(recipients)
        self.assertEqual(
            bounced_emails,
            {
                self.SUPPRESSED_BOUNCE,
                self.UNDETERMINED_BOUNCE,
                self.GENERAL_ABOVE_THRESH,
                self.COMPLAINT,
                self.NO_META_BOUNCE,
            }
        )
