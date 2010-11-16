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

    def testCreateCompleteWebUser(self):
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
        couch_user.add_domain_account('username1','domain1')
        self.assertEqual(couch_user.domain_accounts[0].username, 'username1')
        self.assertEqual(couch_user.domain_accounts[0].domain, 'domain1')
        couch_user.add_domain_account('username2','domain2')
        self.assertEqual(couch_user.domain_accounts[1].username, 'username2')
        self.assertEqual(couch_user.domain_accounts[1].domain, 'domain2')
        couch_user.add_commcare_account('username3','password3','domain3')
        self.assertEqual(couch_user.commcare_accounts[0].username, 'username3')
        self.assertEqual(couch_user.commcare_accounts[0].domain, 'domain3')
        couch_user.add_commcare_account('username4','password4','domain4')
        self.assertEqual(couch_user.commcare_accounts[1].username, 'username4')
        self.assertEqual(couch_user.commcare_accounts[1].domain, 'domain4')
        couch_user.add_phone_device('IMEI')
        self.assertEqual(couch_user.phone_devices[0].IMEI, 'IMEI')
        couch_user.add_phone_number('1234567890')
        self.assertEqual(couch_user.phone_numbers[0].number, '1234567890')
        couch_user.save()

