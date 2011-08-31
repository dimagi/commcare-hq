#from django.test import TestCase
#from corehq.apps.users.models import CouchUser
#from corehq.apps.users.signals import create_user_from_commcare_registration, REGISTRATION_XMLNS
#
#class SignalsTestCase(TestCase):
#
#    def setUp(self):
#        all_users = CouchUser.all()
#        for user in all_users:
#            user.delete()
#        class Mock(dict):
#            def __getattr__(self, attr):
#                return self[attr]
#            def __setattr__(self, attr, value):
#                self[attr] = value
#        self.sender = Mock()
#        # creating a mock xform submission
#        self.xform = Mock()
#        self.xform.xmlns = REGISTRATION_XMLNS
#        self.xform.domain = 'mockdomain'
#        self.xform.form = Mock()
#        self.xform.form.meta = Mock()
#        self.username = 'username'
#        self.device_ID = 'DeviceID'
#        self.uid = 'commcare_user_uuid'
#        self.xform.form.meta.username = self.username
#        self.xform.form.meta.deviceID = self.device_ID
#        self.xform.form.meta.uid = self.uid
#
#    def testNewUserFromFormSubmission(self):
#        """
#        test that a user is automatically created when a submission is received
#        """
#        create_user_from_commcare_registration(self.sender, self.xform)
#        all_users = CouchUser.all()
#        self.assertEqual(len(all_users),1)
#        user = CouchUser.all().one()
#        self.assertEqual(user.username, self.username)
#        self.assertEqual(user.domain, self.xform.domain)
#        self.assertEqual(user.user_id, self.uid)
#        self.assertEqual(user.device_ids[0],self.device_ID)
#
##    def testUpdatePhoneNumberFromFormSubmission(self):
##        """
##        """
##        # create an hq user
##        couch_user = CouchUser()
##
###        django_user = User(username=self.username)
###        django_user.set_password('foo')
###        django_user.save()
###        couch_user = django_user.get_profile().get_couch_user()
##
##        other_device_ID = 'otherdeviceid'
##        couch_user.add_device_id(other_device_ID)
##        #couch_user.add_commcare_username(self.xform.domain, self.username)
##        couch_user.create_commcare_user(self.xform.domain, self.username, 'password')
##        couch_user.save()
##        # TODO: add this back in once we've merged back the refactored users code
##        # all_users = CouchUser.view("users/all_users")
##        # self.assertEqual(len(all_users),1)
##
##        # submit an xform with username and domain, but different phone numbers
##        populate_user_from_commcare_submission(self.sender, self.xform)
##        all_users = CouchUser.all()
##        # TODO: add this back in once we've merged back the refactored users code
##        # self.assertEqual(len(all_users),1)
##        #user = all_users.one()
##        #self.assertEqual(len(user.commcare_accounts),1)
##        #self.assertEqual(user.commcare_accounts[0].django_user.username,self.username)
##        #self.assertEqual(user.commcare_accounts[0].domain,self.xform.domain)
##        #self.assertEqual(user.phone_devices[0].IMEI, other_device_ID)
##        #self.assertEqual(user.phone_devices[1].IMEI, self.device_ID)
##        # user should not be associated with any django accounts, since we don't have passwords
##        #self.assertEqual(user.django_user.username,None)
##
###    def testErrorFromDuplicateUsernameDomainCombo(self):
###        populate_user_from_commcare_submission(self.sender, self.xform)
