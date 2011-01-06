from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser
from corehq.apps.users.models import create_commcare_user_without_django_login

class PhoneUsersTestCase(TestCase):
    
    def setUp(self):
        all_users = CouchUser.view("users/all_users")
        for user in all_users:
            user.delete()
        self.name = 'name'
        self.user = User(username=self.name)
        self.user.set_password('password')
        self.user.save()
        self.domain = 'mockdomain'
        self.couch_user = self.user.get_profile().get_couch_user()
        self.couch_user.add_domain_membership(self.domain)

    def testPhoneUsersViewNoNumberSet(self):
        phone_users_count = CouchUser.view("users/phone_users_by_domain", 
                                           key=self.domain).count()
        self.assertEquals(phone_users_count, 0)

    def testPhoneUsersViewLastNumberAdded(self):
        self.couch_user.add_phone_number(123)
        self.couch_user.add_phone_number(456)
        self.couch_user.save()
        phone_user = CouchUser.view("users/phone_users_by_domain", 
                                    key=self.domain).one()
        self.assertEquals(phone_user['name'], self.name)
        self.assertEquals(phone_user['phone_number'], '456')

    def testPhoneUsersViewDefaultNumber(self):
        self.couch_user.add_phone_number(789)
        self.couch_user.add_phone_number(101, is_default=True)
        self.couch_user.add_phone_number(112)
        self.couch_user.save()
        phone_user = CouchUser.view("users/phone_users_by_domain", 
                                    key=self.domain).one()
        self.assertEquals(phone_user['name'], self.name)
        self.assertEquals(phone_user['phone_number'], '101')

    def testPhoneUsersViewLastCommCareUsername(self):
        self.couch_user.delete()
        phone_user_count = CouchUser.view("users/phone_users_by_domain", 
                                          key=self.domain).count()
        self.assertEquals(phone_user_count, 0)
        # create a user without an associated django account
        couch_user = create_commcare_user_without_django_login(domain = self.domain, 
                                                           username = 'commcare_username',
                                                           uuid = 'commcare_username_uuid')
        couch_user.add_domain_membership(self.domain)
        couch_user.add_phone_number(123)
        couch_user.save()
        # verify no name is returned in phone_users view
        phone_user_count = CouchUser.view("users/phone_users_by_domain", 
                                          key=self.domain).count()
        self.assertEquals(phone_user_count, 1)
        phone_user = CouchUser.view("users/phone_users_by_domain", 
                                    key=self.domain).one()
        self.assertEquals(phone_user['name'], 'commcare_username')
        # add a commcare account and verify commcare username is returned
        couch_user.add_commcare_username(self.domain,'commcare_username_2', 'commcare_account_uuid')
        couch_user.save()
        phone_user = CouchUser.view("users/phone_users_by_domain", 
                                    key=self.domain).one()
        self.assertEquals(phone_user['name'], 'commcare_username_2')
