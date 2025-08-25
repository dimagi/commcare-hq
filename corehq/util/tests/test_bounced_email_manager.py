import datetime
import email
import os

from dateutil.tz import tzlocal
from django.test import SimpleTestCase

from corehq.util.bounced_email_manager import BouncedEmailManager
from corehq.util.models import AwsMeta
from corehq.util.test_utils import TestFileMixin


class TestBouncedEmailManager(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'email')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.manager = BouncedEmailManager()

    def _get_message(self, filename):
        bounce_file = self.get_path(filename, 'txt')
        with open(bounce_file, "r") as f:
            bounce_email = f.read()
            message = email.message_from_string(bounce_email)
        return message

    def test_recipients_standard_aws_bounce(self):
        aws_bounce = self._get_message('standard_aws_bounce')
        self.assertEqual(
            self.manager._get_raw_bounce_recipients(aws_bounce),
            [
                'bouncedemail+fake-project@dimagi.com',
                'bouncedemail+fake@dimagi.com'
            ]
        )

    def test_recipients_email_delivery_failure(self):
        delivery_failure = self._get_message('email_delivery_failure')
        self.assertEqual(
            self.manager._get_raw_bounce_recipients(delivery_failure),
            ['fakeemail5555@sydney.edu.au']
        )

    def test_recipients_yahoo_qmail(self):
        yahoo_qmail = self._get_message('yahoo_qmail_failure')
        self.assertEqual(
            self.manager._get_raw_bounce_recipients(yahoo_qmail),
            ['fakemail555@yahoo.com.br']
        )

    def test_recipients_forwarded_bounce(self):
        forwarded_bounce = self._get_message('forwarded_bounce')
        self.assertEqual(
            self.manager._get_raw_bounce_recipients(forwarded_bounce),
            ['bouncedemail@gmail.com']
        )

    def test_recipients_exchange_bounce(self):
        exchange_bounce = self._get_message('exchange_bounce')
        self.assertEqual(
            self.manager._get_raw_bounce_recipients(exchange_bounce),
            ['bouncedemail@fakecompany.org']
        )

    def test_recipients_auto_reply(self):
        out_of_office = self._get_message('out_of_office')
        self.assertEqual(
            self.manager._get_raw_bounce_recipients(out_of_office),
            None
        )

    def test_sns_bounce_suppressed(self):
        sns_bounce_suppressed = self._get_message('sns_bounce_suppressed')
        self.assertEqual(
            self.manager._get_aws_info(sns_bounce_suppressed, 333),
            [
                AwsMeta(
                    notification_type='Bounce',
                    main_type='Permanent',
                    sub_type='Suppressed',
                    email='fakejoe@gmail.com',
                    reason='Amazon SES has suppressed sending to this address '
                           'because it has a recent history of bouncing as an '
                           'invalid address. For more information about how '
                           'to remove an address from the suppression list, '
                           'see the Amazon SES Developer Guide: '
                           'http://docs.aws.amazon.com/ses/latest/'
                           'DeveloperGuide/remove-from-suppressionlist.html ',
                    headers={
                        'from': ['commcarehq-noreply-production@dimagi.com'],
                        'date': 'Tue, 28 Jan 2020 10:40:04 -0000',
                        'to': ['fakejoe@gmail.com'],
                        'messageId': '<redacted>',
                        'subject': 'Late'
                    },
                    timestamp=datetime.datetime(
                        2020, 1, 28, 10, 40, 4, 931000,
                        tzinfo=tzlocal()
                    ),
                    destination=['fakejoe@gmail.com']
                )
            ]
        )

    def test_sns_bounce_general(self):
        sns_bounce_general = self._get_message('sns_bounce_general')
        self.assertEqual(
            self.manager._get_aws_info(sns_bounce_general, 333),
            [
                AwsMeta(
                    notification_type='Bounce',
                    main_type='Permanent',
                    sub_type='General',
                    email='fake@gmail.com',
                    reason="smtp; 550-5.1.1 The email account that you tried "
                           "to reach does not exist. Please try\n550-5.1.1 "
                           "double-checking the recipient's email address for "
                           "typos or\n550-5.1.1 unnecessary spaces. Learn more"
                           " at\n550 5.1.1  https://support.google.com/mail/?p="
                           "NoSuchUser h6si12061056qtp.98 - gsmtp",
                    headers={
                        'returnPath': 'commcarehq-bounces+production@dimagi.com',
                        'from': ['commcarehq-noreply-production@dimagi.com'],
                        'date': 'Tue, 28 Jan 2020 09:29:02 -0000',
                        'to': ['fake@gmail.com'],
                        'messageId': '<redacted>',
                        'subject': 'Activate your CommCare project'
                    },
                    timestamp=datetime.datetime(
                        2020, 1, 28, 9, 29, 3, 30000,
                        tzinfo=tzlocal()
                    ),
                    destination=['fake@gmail.com']
                )
            ]
        )

    def test_sns_bounce_transient(self):
        sns_bounce_transient = self._get_message('sns_bounce_transient')
        self.assertEqual(
            self.manager._get_aws_info(sns_bounce_transient, 333),
            [
                AwsMeta(
                    notification_type='Bounce',
                    main_type='Transient',
                    sub_type='General',
                    email='fakemail@nd.edu',
                    reason=None,
                    headers={
                        'returnPath': 'commcarehq-bounces+production@dimagi.com',
                        'from': ['commcarehq-noreply-production@dimagi.com'],
                        'date': 'Tue, 28 Jan 2020 13:00:27 -0000',
                        'to': ['fakemail@nd.edu'],
                        'messageId': '<redacted>',
                        'subject': 'Scheduled report from CommCare'
                    },
                    timestamp=datetime.datetime(
                        2020, 1, 28, 13, 0, 35,
                        tzinfo=tzlocal()
                    ),
                    destination=['fakemail@nd.edu']
                )
            ]
        )

    def test_sns_bounce_complaint(self):
        sns_complaint = self._get_message('sns_complaint')
        self.assertEqual(
            self.manager._get_aws_info(sns_complaint, 333),
            [
                AwsMeta(
                    notification_type='Complaint',
                    main_type=None, sub_type='',
                    email='fake@hotmail.co.uk',
                    reason=None,
                    headers={},
                    timestamp=datetime.datetime(
                        2020, 1, 8, 8, 6, 45,
                        tzinfo=tzlocal()
                    ),
                    destination=['fake@hotmail.co.uk']
                )
            ]
        )
