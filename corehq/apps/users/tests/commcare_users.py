from datetime import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from corehq.apps.users.models import CouchUser, COUCH_USER_AUTOCREATED_STATUS
from corehq.apps.users.signals import create_hq_user_from_commcare_registration_info

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
        couch_user_1 = parent.get_profile().get_couch_user()
        # create child
        commcare_domain = self.domain
        commcare_username = self.commcare_username
        commcare_imei = 'imei'
        commcare_user_data = 'random'
        commcare_user_uuid = 'commcare_user_uuid'
        couch_user_2 = create_commcare_user_without_django_login(domain = commcare_domain, 
                                                          username = commcare_username, 
                                                          uuid = commcare_user_uuid,
                                                          imei = commcare_imei, 
                                                          random_user_info = commcare_user_data,
                                                          status = COUCH_USER_AUTOCREATED_STATUS)
        self.assertEquals(couch_user_2.commcare_accounts[0].registering_phone_id, commcare_imei)
        # associate orphan child with parent
        couch_user_1.link_commcare_account(self.domain, couch_user_2.get_id, self.commcare_username)
        
        # only one instance of an hq user should contain that commcare user
        users_count = CouchUser.view("users/by_commcare_username_domain", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(users_count, 1)
        
        # verify that all the data got copied over correctly
        self.assertEquals(len(couch_user_1.commcare_accounts),1)
        self.assertEquals(couch_user_1.commcare_accounts[0].domain,commcare_domain)
        self.assertEquals(couch_user_1.commcare_accounts[0].django_user.username,commcare_username)
        self.assertEquals(couch_user_1.commcare_accounts[0].registering_phone_id,commcare_imei)
        self.assertEquals(couch_user_1.commcare_accounts[0].user_data['random_user_info'],commcare_user_data)
        
        # verify that the data got cleared from the couch_user_2 properly
        couch_user_2 = CouchUser.get(couch_user_2.get_id) # refresh the couch user
        self.assertEquals(len(couch_user_2.commcare_accounts),0)
        
        # only one instance of that commcare user should exist
        commcare_users_count = CouchUser.view("users/commcare_users_by_domain_username", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(commcare_users_count, 1)
                
    def testStealCommCareUser(self):
        # create parent
        parent = User(username='parent')
        parent.set_password('password')
        parent.save()
        couch_user_1 = parent.get_profile().get_couch_user()
        # child
        couch_user_2 = create_hq_user_from_commcare_registration(self.domain, 
                                                                 self.commcare_username, 
                                                                 'password', 'uuid', 'imei', datetime.now())
        # link
        couch_user_1.link_commcare_account(self.domain, couch_user_2.get_id, self.commcare_username)
        # verify that all the data got copied over correctly
        self.assertEquals(len(couch_user_1.commcare_accounts),1)
        self.assertEquals(couch_user_1.commcare_accounts[0].domain,self.domain)
        self.assertEquals(couch_user_1.commcare_accounts[0].django_user.username,self.commcare_username)
        self.assertTrue(len(couch_user_1.commcare_accounts[0].django_user.password)>0)
        self.assertEquals(couch_user_1.commcare_accounts[0].UUID,'uuid')
        self.assertEquals(couch_user_1.commcare_accounts[0].registering_phone_id,'imei')
        # verify that the data got cleared from the couch_user_2 properly
        couch_user_2 = CouchUser.get(couch_user_2.get_id) # refresh the couch user
        self.assertEquals(len(couch_user_2.commcare_accounts),0)
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
        couch_user_1 = create_hq_user_from_commcare_registration(self.domain, 
                                                               self.commcare_username, 
                                                               'password', 'uuid', 'imei', datetime.now())
        couch_user_1.unlink_commcare_account(self.domain, 0)
        # verify that it's gone from couch_user_1
        self.assertEquals(len(couch_user_1.commcare_accounts),0)
        # only one instance of an hq user should contain that commcare user
        users_count = CouchUser.view("users/by_commcare_username_domain", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(users_count, 1)
        couch_user_2 = CouchUser.view("users/by_commcare_username_domain", key=[self.commcare_username, self.domain]).one()
        self.assertEquals(couch_user_2.commcare_accounts[0].domain,self.domain)
        self.assertEquals(couch_user_2.commcare_accounts[0].django_user.username,self.commcare_username)
        self.assertTrue(len(couch_user_2.commcare_accounts[0].django_user.password)>0)
        self.assertEquals(couch_user_2.commcare_accounts[0].UUID,'uuid')
        self.assertEquals(couch_user_2.commcare_accounts[0].registering_phone_id,'imei')
        # only one instance of that commcare user should exist
        commcare_users_count = CouchUser.view("users/commcare_users_by_domain_username", key=[self.domain, self.commcare_username]).total_rows
        self.assertEquals(commcare_users_count, 1)
        users_count = CouchUser.view("users/all_users").total_rows
        self.assertEquals(users_count, 2)

    def testUnlinkCommCareUser(self):
        # create parent and child
        commcare_username = 'username3'
        password = 'password3'
        domain = 'domain3'
        user_1 = User(username='parent')
        user_1.set_password('password')
        user_1.save()
        couch_user_1 = user_1.get_profile().get_couch_user()
        couch_user_1.create_commcare_user(domain, commcare_username, password, uuid='sdf', imei='ewr')
        # unlink
        couch_user_1.unlink_commcare_account(domain, 0)
        # verify
        self.assertEquals(len(couch_user_1.commcare_accounts),0)
        users_count = CouchUser.view("users/by_commcare_username_domain", key=[commcare_username, domain]).total_rows
        self.assertEquals(users_count, 1)
        couch_user_2 = CouchUser.view("users/by_commcare_username_domain", key=[commcare_username, domain]).one()
        self.assertEquals(couch_user_2.commcare_accounts[0].domain,domain)
        self.assertEquals(couch_user_2.commcare_accounts[0].django_user.username,commcare_username)
        self.assertTrue(len(couch_user_2.commcare_accounts[0].django_user.password)>0)
        self.assertEquals(couch_user_2.commcare_accounts[0].UUID,'sdf')
        self.assertEquals(couch_user_2.commcare_accounts[0].registering_phone_id,'ewr')
        # only one instance of that commcare user should exist
        commcare_users_count = CouchUser.view("users/commcare_users_by_domain_username", key=[domain, commcare_username]).total_rows
        self.assertEquals(commcare_users_count, 1)
        users_count = CouchUser.view("users/all_users").total_rows
        self.assertEquals(users_count, 2)
