from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser, WebUser

class UpdateTestCase(TestCase):
    
    def setUp(self):
        all_users = CouchUser.all()
        for user in all_users:
            user.delete()
        User.objects.all().delete()
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        self.couch_user = WebUser.create(None, username, email, password)
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
