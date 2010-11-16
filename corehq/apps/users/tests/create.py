from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.domain.models import Domain

class UsersTestCase(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testCreateBasicWebUser(self):
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        # create django user
        new_user = User.objects.create_user(username, email, password)
        new_user.save()
        # the following will throw a HQUserProfile.DoesNotExist error
        # if the profile was not properly created
        profile = new_user.get_profile()
        # verify that the default couch stuff was created
        couch_user = profile.get_couch_user()
        self.assertEqual(couch_user.django_user.username, username)
        self.assertEqual(couch_user.django_user.email, email)
