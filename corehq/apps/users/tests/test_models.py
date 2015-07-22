from django.test import SimpleTestCase
from corehq.apps.users.models import WebUser, CommCareUser, CouchUser


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
