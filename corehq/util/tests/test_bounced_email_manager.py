import email
import os

from django.test import SimpleTestCase

from corehq.util.bounced_email_manager import BouncedEmailManager
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
