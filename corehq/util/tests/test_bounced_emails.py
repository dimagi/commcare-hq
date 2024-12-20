import datetime

from django.test import TestCase, override_settings

from corehq.util.email_event_utils import get_bounced_system_emails
from dimagi.utils.django.email import get_valid_recipients
from corehq.toggles import (
    BLOCKED_EMAIL_DOMAIN_RECIPIENTS,
    NAMESPACE_EMAIL_DOMAIN,
    BLOCKED_DOMAIN_EMAIL_SENDERS,
    NAMESPACE_DOMAIN,
)
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
    BLOCKED_BY_TOGGLE = 'foobar@thisisatestemail1111.com'
    BAD_FORMAT_MISSING_TLD = 'foobar@gmail'
    BAD_FORMAT_MISSING_AT = 'foobargmail.com'
    SYSTEM_EMAIL = 'system_email_dont_bounce@dimagi.com'

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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_permanent_meta(
            cls.SUPPRESSED_BOUNCE,
            BounceSubType.SUPPRESSED
        )
        cls._create_permanent_meta(
            cls.UNDETERMINED_BOUNCE,
            BounceSubType.UNDETERMINED
        )
        cls._create_permanent_meta(
            cls.GENERAL_BOUNCE,
            BounceSubType.GENERAL
        )
        cls._create_permanent_meta(
            cls.GENERAL_AT_TRESH,
            BounceSubType.GENERAL,
            BOUNCE_EVENT_THRESHOLD,
        )
        cls._create_permanent_meta(
            cls.GENERAL_ABOVE_THRESH,
            BounceSubType.GENERAL,
            BOUNCE_EVENT_THRESHOLD + 1,
        )
        cls._create_permanent_meta(
            cls.SYSTEM_EMAIL,
            BounceSubType.GENERAL,
            BOUNCE_EVENT_THRESHOLD + 1,
        )

        legacy_email = BouncedEmail.objects.create(
            email=cls.LEGACY_BOUNCE,
            created=LEGACY_BOUNCE_MANAGER_DATE - datetime.timedelta(days=1)
        )
        legacy_email.created = LEGACY_BOUNCE_MANAGER_DATE - datetime.timedelta(days=1)
        legacy_email.save()

        complaint_email = BouncedEmail.objects.create(email=cls.COMPLAINT)
        ComplaintBounceMeta.objects.create(
            bounced_email=complaint_email,
            timestamp=datetime.datetime.now(),
        )

        BLOCKED_EMAIL_DOMAIN_RECIPIENTS.set(
            'thisisatestemail1111.com', True, namespace=NAMESPACE_EMAIL_DOMAIN
        )
        cls.bad_domain = 'bad-domain'
        BLOCKED_DOMAIN_EMAIL_SENDERS.set(
            cls.bad_domain, True, namespace=NAMESPACE_DOMAIN
        )

    def setUp(self):
        super().setUp()
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

    def tearDown(self):
        TransientBounceEmail.objects.all().delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        BLOCKED_EMAIL_DOMAIN_RECIPIENTS.set(
            'thisisatestemail1111.com', False, namespace=NAMESPACE_EMAIL_DOMAIN
        )
        BLOCKED_DOMAIN_EMAIL_SENDERS.set(
            cls.bad_domain, False, namespace=NAMESPACE_DOMAIN
        )
        ComplaintBounceMeta.objects.all().delete()
        PermanentBounceMeta.objects.all().delete()
        BouncedEmail.objects.all().delete()
        super().tearDownClass()

    @override_settings(SOFT_ASSERT_EMAIL=SYSTEM_EMAIL)
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
            self.BLOCKED_BY_TOGGLE,
            self.BAD_FORMAT_MISSING_TLD,
            self.BAD_FORMAT_MISSING_AT,
            self.SYSTEM_EMAIL,
        ]

        bounced_emails = BouncedEmail.get_hard_bounced_emails(recipients)
        self.assertEqual(
            bounced_emails,
            {
                self.SUPPRESSED_BOUNCE,
                self.UNDETERMINED_BOUNCE,
                self.GENERAL_ABOVE_THRESH,
                self.TRANSIENT_ABOVE_THRESH,
                self.COMPLAINT,
                self.LEGACY_BOUNCE,
                self.BLOCKED_BY_TOGGLE,
                self.BAD_FORMAT_MISSING_TLD,
                self.BAD_FORMAT_MISSING_AT,
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

    @override_settings(SOFT_ASSERT_EMAIL=SYSTEM_EMAIL)
    def test_get_bounced_system_emails(self):
        self.assertEqual(get_bounced_system_emails(), [self.SYSTEM_EMAIL])

    def test_get_valid_recipients(self):
        recipients = [
            'imok@gmail.com',
            'foo@gmail.com',
            'jdoe@dimagi.com',
        ]
        self.assertEqual(
            get_valid_recipients(recipients),
            recipients
        )
        self.assertEqual(
            get_valid_recipients(recipients, domain='not-blocked-domain'),
            recipients
        )
        self.assertEqual(
            get_valid_recipients(recipients, domain=self.bad_domain, is_conditional_alert=True),
            []
        )
