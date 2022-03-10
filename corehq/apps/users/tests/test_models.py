from datetime import datetime
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Invitation,
    WebUser,
)

from corehq.apps.domain.models import Domain


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
            Invitation(domain='domain_1', email='email2@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow(), is_accepted=True),
            Invitation(domain='domain_2', email='email3@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow()),
        ]
        for inv in cls.invitations:
            inv.save()

    def test_by_domain(self):
        self.assertEqual(len(Invitation.by_domain('domain_1')), 1)
        self.assertEqual(len(Invitation.by_domain('domain_1', is_accepted=True)), 2)
        self.assertEqual(len(Invitation.by_domain('domain_2')), 1)
        self.assertEqual(len(Invitation.by_domain('domain_3')), 0)

    def test_by_email(self):
        self.assertEqual(len(Invitation.by_email('email1@email.com')), 1)
        self.assertEqual(len(Invitation.by_email('email3@email.com')), 1)
        self.assertEqual(len(Invitation.by_email('email4@email.com')), 0)

    @classmethod
    def tearDownClass(cls):
        for inv in cls.invitations:
            inv.delete()
        super(InvitationTest, cls).tearDownClass()


class User_MessagingDomain_Tests(SimpleTestCase):
    def test_web_user_with_no_messaging_domain_returns_false(self):
        user = WebUser(domains=['domain_no_messaging_1', 'domain_no_messaging_2'])
        self.assertFalse(user.belongs_to_messaging_domain())

    def test_web_user_with_messaging_domain_returns_true(self):
        user = WebUser(domains=['domain_no_messaging_1', 'domain_with_messaging', 'domain_no_messaging_2'])
        self.assertTrue(user.belongs_to_messaging_domain())

    def test_commcare_user_is_compatible(self):
        user = CommCareUser(domain='domain_no_messaging_1')
        self.assertFalse(user.belongs_to_messaging_domain())

    def setUp(self):
        self.domains = {
            'domain_no_messaging_1': Domain(granted_messaging_access=False),
            'domain_no_messaging_2': Domain(granted_messaging_access=False),
            'domain_with_messaging': Domain(granted_messaging_access=True),
        }

        patcher = patch.object(Domain, 'get_by_name', side_effect=self._get_domain_by_name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _get_domain_by_name(self, name):
        return self.domains[name]
