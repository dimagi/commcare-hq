from django.test import TestCase
from corehq.apps.users.models import CouchUser, WebUser

class PhoneUsersTestCase(TestCase):
    
    def setUp(self):
        all_users = CouchUser.all()
        for user in all_users:
            user.delete()
        self.username = 'username'
        self.password = 'password'
        self.domain = 'mockdomain'
        self.couch_user = WebUser.create(self.domain, self.username, self.password)
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
#        self.assertEquals(phone_user['name'], self.username)
#        self.assertEquals(phone_user['phone_number'], '456')

    def testPhoneUsersViewDefaultNumber(self):
        self.couch_user.add_phone_number(789)
        self.couch_user.add_phone_number(101, default=True)
        self.couch_user.add_phone_number(112)
        self.couch_user.save()
        phone_user = CouchUser.phone_users_by_domain(self.domain).one()

        self.assertEquals(phone_user.username, self.username)
        self.assertEquals(phone_user.default_phone_number, '101')

    def testPhoneUsersViewLastCommCareUsername(self):
        self.couch_user.delete()
        phone_user_count = CouchUser.phone_users_by_domain(self.domain).count()
        self.assertEquals(phone_user_count, 0)

        couch_user = WebUser.create(self.domain, 'commcare_username_2', 'password')
        couch_user.add_phone_number(123)
        couch_user.save()

        phone_user_count = CouchUser.phone_users_by_domain(self.domain).count()
        self.assertEquals(phone_user_count, 1)
        phone_user = CouchUser.phone_users_by_domain(self.domain).one()
        self.assertEquals(phone_user.username, 'commcare_username_2')
