from django.contrib.auth.models import User
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser, CommCareUser

class SyncWebUserTestCase(TestCase):
    def setUp(self):
        domain = 'test'
        username = "mr-danny@dimagi.com"
        password = "s3cr3t"
        self.domain_obj = create_domain(domain)
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

    def test_truncates_long_names_from_couch_to_django(self):
        # Should truncate name in Django but not in couch
        self.web_user.first_name = 'b'*50
        self.web_user.email = "droberts@dimagi.com"
        self.web_user.save()
        django_user = self.web_user.get_django_user()

        self.assertEqual(len(django_user.first_name), 30)

        # name in django shouldn't sync
        django_user.first_name = "danny"
        django_user.save()
        self.assertEqual(len(self.web_user.first_name), 50)

    def tearDown(self):
        WebUser.get_by_user_id(self.web_user.user_id).delete()
        self.domain_obj.delete()

class SyncCommCareUserTestCase(TestCase):
    def setUp(self):
        self.domain = 'test'
        self.username = "mr-danny@test.commcarehq.org"
        self.password = "s3cr3t"
        self.domain_obj = create_domain(self.domain)
        self.commcare_user = CommCareUser.create(self.domain, self.username, self.password)
        self.commcare_user.save()

    def test_couch_to_django(self):
        self.commcare_user.email = "droberts@dimagi.com"
        self.commcare_user.save()
        self.assertEqual(self.commcare_user.email, self.commcare_user.get_django_user().email)

    def test_django_to_couch(self):
        django_user = self.commcare_user.get_django_user()
        django_user.email = "dr-oberts@dimagi.com"
        django_user.save()
        self.assertEqual(django_user.email, CommCareUser.from_django_user(django_user).email)

    def test_truncates_long_names_from_couch_to_django(self):
        # Should truncate name in Django but not in couch
        self.commcare_user.first_name = 'b'*50
        self.commcare_user.email = "droberts@dimagi.com"
        self.commcare_user.save()
        django_user = self.commcare_user.get_django_user()

        self.assertEqual(len(django_user.first_name), 30)

        # name in django shouldn't sync
        django_user.first_name = "danny"
        django_user.save()
        self.assertEqual(len(self.commcare_user.first_name), 50)

    def test_retire(self):
        self.commcare_user.retire()
        self.assertEqual(User.objects.filter(username=self.commcare_user.username).count(), 0)

        self.commcare_user = CommCareUser.create(self.domain, self.username, self.password)
        self.commcare_user.save()

    def tearDown(self):
        CommCareUser.get_by_user_id(self.commcare_user.user_id).delete()
        self.domain_obj.delete()
