from __future__ import absolute_import
from django.test import TestCase
from django.contrib.auth.models import User

from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.domain.models import Domain


class UpdateTestCase(TestCase):

    def setUp(self):
        super(UpdateTestCase, self).setUp()
        delete_all_users()
        self.username = "joe@my-domain.commcarehq.org"
        password = "password"
        self.domain = Domain(name='my-domain')
        self.domain.save()
        self.couch_user = CommCareUser.create(self.domain.name, self.username, password)
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
