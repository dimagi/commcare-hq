from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser
from corehq.apps.users.signals import populate_user_from_commcare_submission

class SignalsTestCase(TestCase):
    
    def setUp(self):
        all_users = CouchUser.view("users/all_users")
        for user in all_users:
            user.delete()
        class Mock():
            pass        
        self.sender = Mock()
        # creating a mock xform submission
        self.xform = Mock()
        self.xform.domain = 'mockdomain'
        self.xform.form = Mock()
        self.xform.form.meta = Mock()
        self.username = 'username'
        self.device_ID = 'DeviceID'
        self.uid = 'commcare_user_uuid'
        self.xform.form.meta.username = self.username
        self.xform.form.meta.deviceID = self.device_ID
        self.xform.form.meta.uid = self.uid
        
    def testNewUserFromFormSubmission(self):
        """ 
        test that a user is automatically created when a submission is received
        """
        populate_user_from_commcare_submission(self.sender, self.xform)
        all_users = CouchUser.view("users/all_users")
        self.assertEqual(len(all_users),1)
        user = CouchUser.view("users/all_users").one()
        self.assertEqual(user.commcare_accounts[0].django_user.username,self.username)
        self.assertEqual(user.commcare_accounts[0].domain,self.xform.domain)
        self.assertEqual(user.commcare_accounts[0].UUID, self.uid)
        self.assertEqual(user.phone_devices[0].IMEI,self.device_ID)
        # user should not be associated with any django accounts, since we don't have passwords
        self.assertEqual(user.django_user.username,None)
        self.assertEqual(len(user.commcare_accounts),1)

    def testUpdatePhoneNumberFromFormSubmission(self):
        """ 
        """
        # creat an hq user
        couch_user = CouchUser()
        """
        django_user = User(username=self.username)
        django_user.set_password('foo')
        django_user.save()
        couch_user = django_user.get_profile().get_couch_user()
        """
        other_device_ID = 'otherdeviceid'
        couch_user.add_phone_device(other_device_ID)
        #couch_user.add_commcare_username(self.xform.domain, self.username)
        couch_user.create_commcare_user(self.xform.domain, self.username, 'password')
        couch_user.save()
        all_users = CouchUser.view("users/all_users")
        self.assertEqual(len(all_users),1)
        
        # submit an xform with username and domain, but different phone numbers 
        populate_user_from_commcare_submission(self.sender, self.xform)
        all_users = CouchUser.view("users/all_users")
        self.assertEqual(len(all_users),1)
        user = all_users.one()
        self.assertEqual(len(user.commcare_accounts),1)
        self.assertEqual(user.commcare_accounts[0].django_user.username,self.username)
        self.assertEqual(user.commcare_accounts[0].domain,self.xform.domain)
        self.assertEqual(user.phone_devices[0].IMEI, other_device_ID)
        self.assertEqual(user.phone_devices[1].IMEI, self.device_ID)
        # user should not be associated with any django accounts, since we don't have passwords
        self.assertEqual(user.django_user.username,None)

#    def testErrorFromDuplicateUsernameDomainCombo(self):
#        populate_user_from_commcare_submission(self.sender, self.xform)
