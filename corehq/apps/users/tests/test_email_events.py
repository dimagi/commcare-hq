import os
from datetime import datetime

from dimagi.utils.django.email import COMMCARE_MESSAGE_ID_HEADER

from corehq.apps.users.event_handlers import handle_email_invite_message
from corehq.apps.users.models import Invitation, InvitationStatus
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
