from django.test import TestCase

from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CouchUser, WebUser, CommCareUser
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain


class CreateTestCase(TestCase):

    def setUp(self):
        delete_all_users()

    def testCreateBasicWebUser(self):
        """
        test that a basic couch user gets created when calling CouchUser.from_web_user
        """
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        domain = "test"
        domain_obj = create_domain(domain)
        self.addCleanup(domain_obj.delete)
        couch_user = WebUser.create(domain, username, password, email)
        self.addCleanup(couch_user.delete)

        self.assertEqual(couch_user.domains, [domain])
        self.assertEqual(couch_user.email, email)
        self.assertEqual(couch_user.username, username)

        django_user = couch_user.get_django_user()
        self.assertEqual(django_user.email, email)
        self.assertEqual(django_user.username, username)

    def testCreateCompleteWebUser(self):
        """
        testing couch user internal functions
        """
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        # create django user
        domain1 = create_domain('domain1')
        domain2 = create_domain('domain2')
        self.addCleanup(domain2.delete)
        self.addCleanup(domain1.delete)
        couch_user = WebUser.create(None, username, password, email)
        self.addCleanup(couch_user.delete)
        self.assertEqual(couch_user.username, username)
        self.assertEqual(couch_user.email, email)
        couch_user.add_domain_membership('domain1')
        self.assertEqual(couch_user.domain_memberships[0].domain, 'domain1')
        couch_user.add_domain_membership('domain2')
        self.assertEqual(couch_user.domain_memberships[1].domain, 'domain2')
        django_user = couch_user.get_django_user()
        self.assertEqual(couch_user.user_id, CouchUser.from_django_user(django_user).user_id)


class TestDomainMemberships(TestCase):
    domain = "test-domain"

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete()
        cls.webuser2.delete()
        cls.project.delete()
        cls.domain_obj.delete()
        cls.nodomain_obj.delete()
        super(TestDomainMemberships, cls).tearDownClass()

    @classmethod
    def setUpClass(cls):
        super(TestDomainMemberships, cls).setUpClass()
        w_username = "joe"
        w_email = "joe@domain.com"
        w2_username = "ben"
        w2_email = "ben@domain.com"
        cc_username = "mobby"
        password = "password"
        cls.domain_obj = create_domain(cls.domain)
        cls.nodomain_obj = create_domain('nodomain')
        cls.project = Domain(name=cls.domain)
        cls.project.save()

        cls.webuser = WebUser.create(cls.domain, w_username, password, w_email)
        cls.webuser2 = WebUser.create('nodomain', w2_username, password, w2_email)
        cls.ccuser = CommCareUser.create(cls.domain, cc_username, password)

    def setUp(self):
        # Reload users before each test
        self.webuser = WebUser.get(self.webuser._id)
        self.webuser2 = WebUser.get(self.webuser2._id)
        self.ccuser = CommCareUser.get(self.ccuser._id)

    def testMembershipsOnCreation(self):
        self.assertTrue(self.webuser.is_member_of('test-domain'))
        self.assertTrue(self.ccuser.is_member_of('test-domain'))

    def testGetMemberships(self):
        self.assertEquals(self.webuser.get_domain_membership(self.domain).domain, self.domain)
        self.assertEquals(self.ccuser.get_domain_membership(self.domain).domain, self.domain)

    def testDefaultPermissions(self):
        self.assertFalse(self.webuser.has_permission(self.domain, 'view_reports'))
        self.assertFalse(self.ccuser.has_permission(self.domain, 'view_reports'))

    def testNewRole(self):
        self.webuser.set_role(self.domain, "field-implementer")
        self.ccuser.set_role(self.domain, "field-implementer")
        self.webuser.save()
        self.ccuser.save()
        self.setUp()  # reload users to clear CouchUser.role

        self.assertEquals(self.webuser.get_domain_membership(self.domain).role_id,
                          self.ccuser.get_domain_membership(self.domain).role_id)
        self.assertEquals(self.webuser.role_label(), self.ccuser.role_label())

        self.assertTrue(self.webuser.has_permission(self.domain, 'view_reports'))
        self.assertTrue(self.ccuser.has_permission(self.domain, 'view_reports'))

        self.assertFalse(self.webuser.is_domain_admin(self.domain))
        self.assertFalse(self.ccuser.is_domain_admin(self.domain))

    def testDeleteDomainMembership(self):
        self.webuser.delete_domain_membership(self.domain)

        with self.assertRaises(NotImplementedError):
            self.ccuser.delete_domain_membership(self.domain)

        self.assertFalse(self.webuser.is_member_of(self.domain))
        self.assertFalse(self.webuser2.is_member_of(self.domain))
        self.assertTrue(self.ccuser.is_member_of(self.domain))
        self.assertEquals(self.ccuser.get_domain_membership(self.domain).domain, self.domain)

    def testTransferMembership(self):
        self.webuser.transfer_domain_membership(self.domain, self.webuser2)
        self.assertFalse(self.webuser.is_member_of(self.domain))
        self.assertTrue(self.webuser2.is_member_of(self.domain))
