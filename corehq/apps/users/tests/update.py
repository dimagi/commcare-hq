from django.test import TestCase
from django.contrib.auth.models import User

class CouchUserTestCase(TestCase):
    
    def setUp(self):
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        self.user = User.objects.create_user(username, email, password)
        self.user.save()
        self.couch_user = self.user.get_profile().get_couch_user()
        
    def testAddRemovePhoneNumbers(self):
        """ 
        test that a basic couch user gets created properly after 
        saving a django user programmatically
        """
        self.couch_user.add_phone_number('123123123')
        self.assertEqual(self.couch_user.get_phone_numbers(), ['123123123'])
        self.couch_user.add_phone_number('321321321')
        self.assertEqual(self.couch_user.get_phone_numbers(), ['123123123', '321321321'])

    def testUpdateDjangoUser(self):
        """ 
        test that a basic couch user gets created properly after 
        saving a django user programmatically
        """
        self.user.first_name = "update_first"
        self.user.last_name = "update_last"
        self.user.save()
        self.assertEqual(self.user.get_profile().get_couch_user().django_user.first_name, 'update_first')
        self.assertEqual(self.user.get_profile().get_couch_user().django_user.last_name, 'update_last')

