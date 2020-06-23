from datetime import datetime

from django.test import SimpleTestCase, TestCase

from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Invitation,
    WebUser,
)


class CouchUserTest(SimpleTestCase):

    def test_web_user_flag(self):
        self.assertTrue(WebUser().is_web_user())
        self.assertTrue(CouchUser.wrap(WebUser().to_json()).is_web_user())
        self.assertFalse(CommCareUser().is_web_user())
        self.assertFalse(CouchUser.wrap(CommCareUser().to_json()).is_web_user())
        with self.assertRaises(NotImplementedError):
            CouchUser().is_web_user()

    def test_commcare_user_flag(self):
        self.assertFalse(WebUser().is_commcare_user())
        self.assertFalse(CouchUser.wrap(WebUser().to_json()).is_commcare_user())
        self.assertTrue(CommCareUser().is_commcare_user())
        self.assertTrue(CouchUser.wrap(CommCareUser().to_json()).is_commcare_user())
        with self.assertRaises(NotImplementedError):
            CouchUser().is_commcare_user()


class InvitationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(InvitationTest, cls).setUpClass()
        cls.invitations = [
            Invitation(domain='domain_1', email='email1@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow()),
            Invitation(domain='domain_1', email='email1@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow(), is_accepted=True),
            Invitation(domain='domain_2', email='email2@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow()),
        ]
        for inv in cls.invitations:
            inv.save()

    def test_by_domain(self):
        self.assertEqual(len(Invitation.by_domain('domain_1')), 1)
        self.assertEqual(len(Invitation.by_domain('domain_2')), 1)
        self.assertEqual(len(Invitation.by_domain('domain_3')), 0)

    def test_by_email(self):
        self.assertEqual(len(Invitation.by_email('email1@email.com')), 1)
        self.assertEqual(len(Invitation.by_email('email2@email.com')), 1)
        self.assertEqual(len(Invitation.by_email('email3@email.com')), 0)

    @classmethod
    def tearDownClass(cls):
        for inv in cls.invitations:
            inv.delete()
        super(InvitationTest, cls).tearDownClass()
