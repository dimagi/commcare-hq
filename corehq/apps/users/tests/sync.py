from django.test import TestCase
from corehq.apps.users.models import WebUser

class SyncTestCase(TestCase):
    def setUp(self):
        domain = 'test'
        username = "mr-danny@dimagi.com"
        password = "s3cr3t"
        self.web_user = WebUser.create(domain, username, password)
        self.web_user.save()

    def test_couch_to_django(self):
        self.web_user.email = "droberts@dimagi.com"
        self.web_user.save()
        self.assertEqual(self.web_user.email, self.web_user.get_django_user().email)

    def test_django_to_couch(self):
        django_user = self.web_user.get_django_user()
        django_user.email = "dr-oberts@dimagi.com"
        django_user.save()
        self.assertEqual(django_user.email, WebUser.from_django_user(django_user).email)

    def tearDown(self):
        WebUser.get_by_user_id(self.web_user.user_id)