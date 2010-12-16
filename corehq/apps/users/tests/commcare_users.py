from datetime import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser, COUCH_USER_AUTOCREATED_STATUS
from corehq.apps.users.signals import create_hq_user_from_commcare_registration
from corehq.apps.users.models import create_couch_user_without_web_user

class CommCareUsersTestCase(TestCase):
    
    def setUp(self):
        all_users = CouchUser.view("users/all_users")
        for user in all_users:
            user.delete()
        self.domain = 'mockdomain'
        self.commcare_username = 'commcare_user'

    def testLinkOrphanCommCareUser(self):
        # create parent
        parent = User(username='parent')
        parent.set_password('password')
        parent.save()
        # create child
        create_couch_user_without_web_user(self.domain, 
                                           self.commcare_username, 
                                           'imei', 
                                           COUCH_USER_AUTOCREATED_STATUS)
        # associate orphan child with parent
        parent_couch_user = parent.get_profile().get_couch_user()

        parent_couch_user.link_commcare_account(self.domain, self.commcare_username)
        
        # only one instance of an hq user should contain that commcare user
        users_count = CouchUser.view("users/by_commcare_username_domain", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(users_count, 1)
        
        # only one instance of that commcare user should exist
        commcare_users_count = CouchUser.view("users/commcare_users_by_domain_username", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(commcare_users_count, 1)
        
        # only one instance of an hq user should contain that commcare user
        users_count = CouchUser.view("users/by_commcare_username_domain", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(users_count, 1)

        # we should only have one instance of an hq user. the orphan's hq parent should be deleted
        # (not enforced yet)
        # users = CouchUser.view("users/by_commcare_username_domain", key=[self.domain, self.commcare_username])
        # self.assertEquals(len(users), 1)
        
    def testStealCommCareUser(self):
        # create parent
        parent = User(username='parent')
        parent.set_password('password')
        parent.save()
        parent_couch_user = parent.get_profile().get_couch_user()
        # child
        create_hq_user_from_commcare_registration(self.domain, 
                                                               self.commcare_username, 
                                                               'password', 'uuid', 'imei', datetime.now())
        parent_couch_user.link_commcare_account(self.domain, self.commcare_username)
        # only one instance of that commcare user should exist
        commcare_users = CouchUser.view("users/commcare_users_by_domain_username", key=[self.domain, self.commcare_username])
        self.assertEquals(len(commcare_users), 1)        
        # only one instance of an hq user should contain that commcare user
        users_count = CouchUser.view("users/by_commcare_username_domain", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(users_count, 1)
        users_count = CouchUser.view("users/all_users").total_rows
        self.assertEquals(users_count, 2)

    def testUnlinkOrphanCommCareUser(self):
        # parent
        couch_user = create_hq_user_from_commcare_registration(self.domain, 
                                                               self.commcare_username, 
                                                               'password', 'uuid', 'imei', datetime.now())
        couch_user.unlink_commcare_account(self.domain, 0)
        # only one instance of an hq user should contain that commcare user
        users_count = CouchUser.view("users/by_commcare_username_domain", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(users_count, 1)
        # only one instance of that commcare user should exist
        commcare_users_count = CouchUser.view("users/commcare_users_by_domain_username", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(commcare_users_count, 1)
        users_count = CouchUser.view("users/all_users").total_rows
        self.assertEquals(users_count, 2)
