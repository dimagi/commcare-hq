from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS, SQLLastReadMessage
from corehq.apps.sms.tests.util import BaseSMSTest
from corehq.apps.users.models import CommCareUser
from datetime import datetime
from django.test.client import Client


class ChatTestCase(BaseSMSTest):

    def setUp(self):
        super(ChatTestCase, self).setUp()

        self.domain = 'sms-chat-test-domain'
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()

        self.create_account_and_subscription(self.domain)
        self.domain_obj = Domain.get(self.domain_obj.get_id)

    def tearDown(self):
        self.doCleanups()
        self.domain_obj.delete()
        super(ChatTestCase, self).tearDown()

    def test_last_read_message(self):
        self.assertIsNone(SQLLastReadMessage.by_anyone(self.domain, 'contact-id-1'))
        self.assertIsNone(SQLLastReadMessage.by_user(self.domain, 'user-id-1', 'contact-id-1'))
        self.assertIsNone(SQLLastReadMessage.by_user(self.domain, 'user-id-2', 'contact-id-1'))

        lrm1 = SQLLastReadMessage.objects.create(
            domain=self.domain,
            read_by='user-id-1',
            contact_id='contact-id-1',
            message_id='message-id-1',
            message_timestamp=datetime(2016, 2, 17, 12, 0),
        )
        self.addCleanup(lrm1.delete)

        self.assertEqual(SQLLastReadMessage.by_anyone(self.domain, 'contact-id-1'), lrm1)
        self.assertEqual(SQLLastReadMessage.by_user(self.domain, 'user-id-1', 'contact-id-1'), lrm1)
        self.assertIsNone(SQLLastReadMessage.by_user(self.domain, 'user-id-2', 'contact-id-1'))

        lrm2 = SQLLastReadMessage.objects.create(
            domain=self.domain,
            read_by='user-id-2',
            contact_id='contact-id-1',
            message_id='message-id-2',
            message_timestamp=datetime(2016, 2, 17, 13, 0),
        )
        self.addCleanup(lrm2.delete)

        self.assertEqual(SQLLastReadMessage.by_anyone(self.domain, 'contact-id-1'), lrm2)
        self.assertEqual(SQLLastReadMessage.by_user(self.domain, 'user-id-1', 'contact-id-1'), lrm1)
        self.assertEqual(SQLLastReadMessage.by_user(self.domain, 'user-id-2', 'contact-id-1'), lrm2)
