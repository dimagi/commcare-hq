import os
from datetime import datetime

from unittest.mock import patch

from dimagi.utils.django.email import COMMCARE_MESSAGE_ID_HEADER

from django.core import mail

from corehq.apps.users.event_handlers import handle_email_invite_message
from corehq.apps.users.models import Invitation, InvitationStatus, WebUser, check_and_send_limit_email
from corehq.util.tests.test_email_event_utils import TestSnsEmailBase


class TestInviteMessages(TestSnsEmailBase):
    root = os.path.dirname(__file__)

    def setUp(self):
        super().setUp()

        self.invite = Invitation.objects.create(
            domain='test-domain',
            email='user@test.com',
            invited_by='friend@test.com',
            invited_on=datetime.utcnow(),
        )

    def tearDown(self):
        Invitation.objects.all().delete()
        super().tearDown()

    def test_bounced_event(self):
        message = self._get_message("test_bounced_event")
        for header in message['mail']['headers']:
            if header == COMMCARE_MESSAGE_ID_HEADER:
                header['value'] = self.invite.uuid
                break

        handle_email_invite_message(message, self.invite.uuid)
        invite = Invitation.objects.get(uuid=self.invite.uuid)

        self.assertEqual(invite.email_status, InvitationStatus.BOUNCED)


class TestUserLimitWarnings(TestSnsEmailBase):
    def setUp(self):
        self.domain = 'test_domain'
        self.recipients = ['orange@gmail.com', 'purple@gmail.com']
        self.plan_limit = 100

        get_admins_patcher = patch.object(WebUser, 'get_admins_by_domain')
        self.mock_get_admins = get_admins_patcher.start()
        self.mock_get_admins.return_value = [WebUser(username=self.recipients[0])]
        self.addCleanup(get_admins_patcher.stop)

        billing_admin_patcher = patch.object(WebUser, 'get_billing_admins_by_domain')
        self.mock_get_billing_admins = billing_admin_patcher.start()
        self.mock_get_billing_admins.return_value = [WebUser(username=self.recipients[1])]
        self.addCleanup(billing_admin_patcher.stop)

    def dont_send_email_below_threshold(self):
        # email should not send if user count is still below the 90% threshold
        prev_user_count = 79
        post_user_count = 89
        check_and_send_limit_email(self.domain, self.plan_limit, post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 0)

    def send_warning_email_at_threshold(self):
        # email should send upon reaching/crossing 90% of the plan limit
        prev_user_count = 80
        post_user_count = 90
        check_and_send_limit_email(self.domain, self.plan_limit, post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, self.recipients)
        self.assertEqual(mail.outbox[0].subject,
                         "User count has reached 90% of the Plan limit for {}".format(self.domain))

    def send_final_email_at_threshold(self):
        # email should send upon reaching/crossing the plan limit
        prev_user_count = 90
        post_user_count = 100
        check_and_send_limit_email(self.domain, self.plan_limit, post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, self.recipients)
        self.assertEqual(mail.outbox[0].subject,
                         "User count has reached the Plan limit for {}".format(self.domain))

    def dont_send_email_for_enterprise(self):
        # email shouldn't send when subscribed to the enterprise plan
        enterprise_plan_limit = -1
        prev_user_count = 90
        post_user_count = 100
        check_and_send_limit_email(self.domain, enterprise_plan_limit, post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 0)

    def only_send_warning_email_once(self):
        # the warning email should only send once: when reaching/crossing the 90% threshold
        prev_user_count = 90
        post_user_count = 91
        check_and_send_limit_email(self.domain, self.plan_limit, post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 0)

    def only_send_final_email_once(self):
        # the final email should only send once: when reaching/crossing the 100% threshold
        prev_user_count = 100
        post_user_count = 101
        check_and_send_limit_email(self.domain, self.plan_limit, post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 0)
