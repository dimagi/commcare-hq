import datetime
import json
import os

from django.test import TestCase

from corehq.util.email_event_utils import (
    get_relevant_aws_meta,
    handle_email_sns_event,
)
from corehq.util.models import (
    AwsMeta,
    BouncedEmail,
    BounceSubType,
    ComplaintBounceMeta,
    PermanentBounceMeta,
    TransientBounceEmail,
)
from corehq.util.test_utils import TestFileMixin


class TestSnsEmailBase(TestCase, TestFileMixin):
    file_path = ('data', 'email')
    root = os.path.dirname(__file__)

    def tearDown(self):
        ComplaintBounceMeta.objects.all().delete()
        PermanentBounceMeta.objects.all().delete()
        TransientBounceEmail.objects.all().delete()
        BouncedEmail.objects.all().delete()
        super().tearDown()

    def _get_message(self, filename):
        bounce_file = self.get_path(filename, 'json')
        with open(bounce_file, "r") as f:
            bounce_message = json.loads(f.read())
        return bounce_message


class TestBouncedEmailManager(TestSnsEmailBase):

    def test_scheduled_complaint(self):
        complaint_message = self._get_message('scheduled_complaint')
        self.assertEqual(
            get_relevant_aws_meta(complaint_message),
            [
                AwsMeta(
                    notification_type='Complaint',
                    main_type=None,
                    sub_type=None,
                    email='alicedoe@univeristy.edu',
                    reason=None,
                    headers={
                        'returnPath': 'noreplyemail@company.com',
                        'from': ['noreplyemail@company.com'],
                        'date': 'Thu, 16 Jul 2020 03:02:22 -0000',
                        'to': ['alicedoe@univeristy.edu'],
                        'cc': ['janedoe@company.com'],
                        'messageId': '<redacted@server-name>',
                        'subject': 'Invitation from Alice Doe to join CommCareHQ'
                    },
                    timestamp=datetime.datetime(2020, 7, 16, 3, 16, 55, 129000,
                                                tzinfo=datetime.timezone.utc),
                    destination=[
                        'alicedoe@univeristy.edu',
                        'janedoe@company.com'
                    ]
                ),
                AwsMeta(
                    notification_type='Complaint',
                    main_type=None,
                    sub_type=None,
                    email='janedoe@company.com',
                    reason=None,
                    headers={
                        'returnPath': 'noreplyemail@company.com',
                        'from': ['noreplyemail@company.com'],
                        'date': 'Thu, 16 Jul 2020 03:02:22 -0000',
                        'to': ['alicedoe@univeristy.edu'],
                        'cc': ['janedoe@company.com'],
                        'messageId': '<redacted@server-name>',
                        'subject': 'Invitation from Alice Doe to join CommCareHQ'
                    },
                    timestamp=datetime.datetime(2020, 7, 16, 3, 16, 55, 129000,
                                                tzinfo=datetime.timezone.utc),
                    destination=[
                        'alicedoe@univeristy.edu',
                        'janedoe@company.com'
                    ]
                ),
            ]
        )
        handle_email_sns_event(complaint_message)

        first_bounced_email = BouncedEmail.objects.filter(email='alicedoe@univeristy.edu')
        second_bounced_email = BouncedEmail.objects.filter(email='janedoe@company.com')
        self.assertTrue(first_bounced_email.exists())
        self.assertTrue(second_bounced_email.exists())

        self.assertTrue(
            ComplaintBounceMeta.objects.filter(
                bounced_email=first_bounced_email.first()
            ).exists()
        )
        self.assertTrue(
            ComplaintBounceMeta.objects.filter(
                bounced_email=second_bounced_email.first()
            ).exists()
        )

    def test_scheduled_general_bounce(self):
        bounce_message = self._get_message('scheduled_general_bounce')
        self.assertEqual(
            get_relevant_aws_meta(bounce_message),
            [
                AwsMeta(
                    notification_type='Bounce',
                    main_type='Permanent',
                    sub_type='General',
                    email='permanent_general_bounce@company.org',
                    reason=(
                        'smtp; 550 5.4.1 Recipient address rejected: Access '
                        'denied. AS(redacted) [redacted.outlook.com]'
                    ),
                    headers={
                        'returnPath': 'noreplyemail@company.com',
                        'from': ['noreplyemail@company.com'],
                        'date': 'Fri, 31 Jul 2020 20:09:55 -0000',
                        'to': ['permanent_general_bounce@company.org'],
                        'cc': ['johnDoe@university.edu'],
                        'messageId': '<redacted@server-name>',
                        'subject': 'Invitation from John Doe to join CommCareHQ'
                    },
                    timestamp=datetime.datetime(2020, 7, 31, 20, 9, 56, 637000,
                                                tzinfo=datetime.timezone.utc),
                    destination=[
                        'permanent_general_bounce@company.org',
                        'johnDoe@university.edu'
                    ]
                )
            ]
        )
        handle_email_sns_event(bounce_message)

        bounced_email = BouncedEmail.objects.filter(email='permanent_general_bounce@company.org')
        self.assertTrue(bounced_email.exists())

        permanent_meta = PermanentBounceMeta.objects.filter(bounced_email=bounced_email.first())
        self.assertTrue(permanent_meta.exists())
        self.assertEqual(permanent_meta.first().sub_type, BounceSubType.GENERAL)

    def test_scheduled_suppressed_bounce(self):
        bounce_message = self._get_message('scheduled_suppressed_bounce')
        self.assertEqual(
            get_relevant_aws_meta(bounce_message),
            [
                AwsMeta(
                    notification_type='Bounce',
                    main_type='Permanent',
                    sub_type='Suppressed',
                    email='permanent.suppressed@company.org',
                    reason=(
                        'Amazon SES has suppressed sending to this address '
                        'because it has a recent history of bouncing as an '
                        'invalid address. For more information about how to '
                        'remove an address from the suppression list, see the '
                        'Amazon SES Developer Guide: '
                        'http://docs.aws.amazon.com/ses/latest/DeveloperGuide/'
                        'remove-from-suppressionlist.html '
                    ),
                    headers={
                        'returnPath': 'noreplyemail@company.com',
                        'from': ['noreplyemail@company.com'],
                        'date': 'Tue, 28 Jul 2020 00:28:28 -0000',
                        'to': ['permanent.suppressed@company.org'],
                        'cc': ['john.doe@agency.gov'],
                        'messageId': '<redacted@server-name>',
                        'subject': 'Invitation from John Doe to join CommCareHQ'
                    },
                    timestamp=datetime.datetime(2020, 7, 28, 0, 28, 28, 622000,
                                                tzinfo=datetime.timezone.utc),
                    destination=[
                        'permanent.suppressed@company.org',
                        'john.doe@agency.gov'
                    ]
                )
            ]
        )
        handle_email_sns_event(bounce_message)

        bounced_email = BouncedEmail.objects.filter(email='permanent.suppressed@company.org')
        self.assertTrue(bounced_email.exists())

        permanent_meta = PermanentBounceMeta.objects.filter(bounced_email=bounced_email.first())
        self.assertTrue(permanent_meta.exists())
        self.assertEqual(permanent_meta.first().sub_type, BounceSubType.SUPPRESSED)

    def test_scheduled_transient_bounce(self):
        transient_message = self._get_message('scheduled_transient_bounce')
        transient_email = 'transientEmail@company.org'
        self.assertEqual(
            get_relevant_aws_meta(transient_message),
            [
                AwsMeta(
                    notification_type='Bounce',
                    main_type='Transient',
                    sub_type='General',
                    email='transientEmail@company.org',
                    reason=(
                        'smtp; 554 4.4.7 Message expired: unable to deliver '
                        'in 840 minutes.<421 4.4.0 Unable to lookup DNS for '
                        'company.org>'
                    ),
                    headers={
                        'returnPath': 'noreplyemail@company.com',
                        'from': ['noreplyemail@company.com'],
                        'date': 'Fri, 31 Jul 2020 06:01:50 -0000',
                        'to': ['transientEmail@company.org'],
                        'messageId': '<redacted>',
                        'subject': 'Scheduled report from CommCare HQ'
                    },
                    timestamp=datetime.datetime(2020, 7, 31, 21, 8, 57, 723000,
                                                tzinfo=datetime.timezone.utc),
                    destination=['transientEmail@company.org']
                )
            ]
        )

        handle_email_sns_event(transient_message)

        bounced_email = BouncedEmail.objects.filter(email=transient_email)
        self.assertFalse(bounced_email.exists())

        transient_info = TransientBounceEmail.objects.filter(email=transient_email)
        self.assertTrue(transient_info.exists())

    def test_send_event(self):
        send_event = self._get_message('send_event')
        sender_email = "jdoe@company-associate.com"
        self.assertEqual(get_relevant_aws_meta(send_event), [])

        handle_email_sns_event(send_event)

        bounced_email = BouncedEmail.objects.filter(email=sender_email)
        self.assertFalse(bounced_email.exists())

        transient_info = TransientBounceEmail.objects.filter(email=sender_email)
        self.assertFalse(transient_info.exists())
