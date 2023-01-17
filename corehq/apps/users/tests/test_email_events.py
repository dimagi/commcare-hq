import os
from datetime import datetime

from dimagi.utils.django.email import COMMCARE_MESSAGE_ID_HEADER

from django.core import mail

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.event_handlers import handle_email_invite_message
from corehq.apps.users.models import Invitation, InvitationStatus, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.role_utils import UserRolePresets, initialize_domain_with_default_roles
from corehq.apps.users.views.mobile.users import MobileWorkerListView
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
        self.domain = create_domain("testapp")
        initialize_domain_with_default_roles(self.domain.name)
        self.recipients = ["orange@gmail.com", "purple@gmail.com"]
        self.domain_admin = WebUser.create(self.domain.name, self.recipients[0], "123", None, None, is_admin=True)
        self.domain_admin.save()
        self.billing_admin_user = WebUser.create(self.domain.name, self.recipients[1], "123", None, None)
        role = UserRole.objects.get(domain=self.domain, name=UserRolePresets.BILLING_ADMIN)
        self.billing_admin_user.set_role(self.domain.name, role.get_qualified_id())
        self.billing_admin_user.save()

    def tearDown(self):
        self.domain_admin.delete(self.domain.name, None)
        self.billing_admin_user.delete(self.domain.name, None)
        self.domain.delete()

    def test_limit_emails(self):
        plan_limit = 100

        # email should not send if user count is still below the 90% threshold
        prev_user_count = 75
        post_user_count = 85
        MobileWorkerListView.check_and_send_limit_email(self.domain.name, plan_limit,
                                                        post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 0)

        # email should send upon reaching/crossing 90% of the plan limit
        prev_user_count = 85
        post_user_count = 95
        MobileWorkerListView.check_and_send_limit_email(self.domain.name, plan_limit,
                                                        post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, self.recipients)
        self.assertEqual(mail.outbox[0].subject,
                         "User count has reached 90% of the Plan limit for {}".format(self.domain.name))

        # email should send upon reaching/crossing the plan limit
        prev_user_count = 95
        post_user_count = 100
        MobileWorkerListView.check_and_send_limit_email(self.domain.name, plan_limit,
                                                        post_user_count, prev_user_count)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, self.recipients)
        self.assertEqual(mail.outbox[1].subject,
                         "User count has reached the Plan limit for {}".format(self.domain.name))
