from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser, CommCareUser
from couchforms.models import XFormInstance

class UpdateTestCase(TestCase):
    
    def setUp(self):
        all_users = CouchUser.all()
        for user in all_users:
            user.delete()
        User.objects.all().delete()
        self.username = "joe@my-domain.commcarehq.org"
        password = "password"
        self.domain = 'my-domain'
        self.couch_user = CommCareUser.create(self.domain, self.username, password)
        self.couch_user.save()
        
    def testAddRemovePhoneNumbers(self):
        """ 
        test that a basic couch user gets created properly after 
        saving a django user programmatically
        """
        self.couch_user.add_phone_number('123123123')
        self.assertEqual(self.couch_user.phone_numbers, ['123123123'])
        self.couch_user.add_phone_number('321321321')
        self.assertEqual(self.couch_user.phone_numbers, ['123123123', '321321321'])

    def testChangeUsername(self):
        new_username = 'joe.shmoe@domain.com'
        self.assertEqual(CouchUser.get_by_username(self.username).user_id, self.couch_user.user_id)
        self.assertEqual(User.objects.filter(username=self.username).count(), 1)
        self.couch_user.change_username(new_username)
        self.assertEqual(CouchUser.get_by_username(self.username), None)
        self.assertEqual(CouchUser.get_by_username(new_username).user_id, self.couch_user.user_id)
        self.assertEqual(self.couch_user.get_django_user().username, new_username)
        self.assertEqual(User.objects.filter(username=new_username).count(), 1)
        self.assertEqual(User.objects.get(username=new_username).id, self.couch_user.get_django_user().id)
        self.assertEqual(User.objects.filter(username=self.username).count(), 0)

    def testTransferToDomain(self):
        new_domain = 'my-new-domain'
        xform = XFormInstance(
            domain=self.domain,
            app_id="old-app-id",
            form=dict(
                meta=dict(
                    userID=self.couch_user.user_id
                )
            )
        )
        xform.save()
        self.assertEqual(self.couch_user.form_count, 1)
        self.couch_user.transfer_to_domain(new_domain, app_id="new-app-id")
        self.assertEqual(self.couch_user.form_count, 1)
        self.assertEqual(self.couch_user.domain, new_domain)
        self.assertEqual(self.couch_user.username, self.username.replace(self.domain, new_domain))
        for form in self.couch_user.get_forms():
            self.assertEqual(form.domain, new_domain)
            self.assertEqual(form.app_id, 'new-app-id')
#    def testUpdateDjangoUser(self):
#        """
#        test that a basic couch user gets created properly after
#        saving a django user programmatically
#        """
#        self.user.first_name = "update_first"
#        self.user.last_name = "update_last"
#        self.user.save()
#        self.assertEqual(self.user.get_profile().get_couch_user().django_user.first_name, 'update_first')
#        self.assertEqual(self.user.get_profile().get_couch_user().django_user.last_name, 'update_last')
#
