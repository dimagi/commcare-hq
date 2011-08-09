from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser

class PhoneUsersTestCase(TestCase):
    
    def setUp(self):
        all_users = CouchUser.view("users/all_users", include_docs=True)
        for user in all_users:
            user.delete()
        self.name = 'name'
        self.user = User(username=self.name)
        self.user.set_password('password')
        self.user.save()
        self.domain = 'mockdomain'
        self.couch_user = CouchUser.from_django_user(self.user)
        self.couch_user.add_domain_membership(self.domain)
        self.couch_user.save()

    def testPhoneUsersViewNoNumberSet(self):
        phone_users_count = CouchUser.view("users/phone_users_by_domain", 
                                           key=self.domain).count()
        self.assertEquals(phone_users_count, 0)

#    def testPhoneUsersViewLastNumberAdded(self):
#        self.couch_user.add_phone_number(123)
#        self.couch_user.add_phone_number(456)
#        self.couch_user.save()
#        phone_user = CouchUser.view("users/phone_users_by_domain",
#            startkey=[self.domain],
#            endkey=[self.domain, {}],
#            include_docs=True,
#        ).one()
#        self.assertEquals(phone_user['name'], self.name)
#        self.assertEquals(phone_user['phone_number'], '456')

    def testPhoneUsersViewDefaultNumber(self):
        self.couch_user.add_phone_number(789)
        self.couch_user.add_phone_number(101, default=True)
        self.couch_user.add_phone_number(112)
        self.couch_user.save()
        phone_user = CouchUser.phone_users_by_domain(self.domain).one()

        self.assertEquals(phone_user.default_account.login.username, self.name)
        self.assertEquals(phone_user.default_phone_number, '101')

    def testPhoneUsersViewLastCommCareUsername(self):
        self.couch_user.delete()
        phone_user_count = CouchUser.phone_users_by_domain(self.domain).count()
        self.assertEquals(phone_user_count, 0)
        # create a user without an associated django account
        couch_user = CouchUser()
        couch_user.add_domain_membership(self.domain)
        couch_user.add_phone_number(123)
        couch_user.save()
        # verify no name is returned in phone_users view
        phone_user_count = CouchUser.phone_users_by_domain(self.domain).count()
        self.assertEquals(phone_user_count, 1)
        phone_user = CouchUser.phone_users_by_domain(self.domain).one()

        self.assertEquals(phone_user.default_account, None)
        
        # add a commcare account and verify commcare username is returned
        user = User(username='commcare_username_2')
        user.save()
        couch_user.add_commcare_account(user, self.domain, 'device_id', user_data={})
        couch_user.save()
        phone_user = CouchUser.phone_users_by_domain(self.domain).one()
        self.assertEquals(phone_user.username, 'commcare_username_2')
