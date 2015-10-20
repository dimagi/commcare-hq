from django.test import TestCase
from corehq.apps.users.util import format_username
from corehq.util.dates import iso_string_to_date
from couchforms.models import XFormInstance
from corehq.apps.users.models import CouchUser, WebUser, CommCareUser
from dimagi.utils.dates import force_to_datetime
from django.contrib.auth.models import User
from casexml.apps.phone.xml import USER_REGISTRATION_XMLNS,\
    USER_REGISTRATION_XMLNS_DEPRECATED
from corehq.apps.domain.models import Domain


class CreateTestCase(TestCase):

    def setUp(self):
        all_users = CouchUser.all()
        for user in all_users:
            user.delete()
        self.xform = XFormInstance()
        self.xform.form = {}
        self.xform.form['username'] = self.username     = 'test_reg'
        self.xform.form['password'] = self.password     = '1982'
        self.xform.form['uuid']     = self.uuid         = 'BXPKZLP49P3DDTJH3W0BRM2HV'
        self.xform.form['date']     = self.date_string  = '2010-03-23'
        self.xform.form['registering_phone_id'] = self.registering_device_id = '67QQ86GVH8CCDNSCL0VQVKF7A'
        self.xform.form['user_data'] = {'data': [{'@key': 'user_type', '#text': 'normal'}]}
        self.xform.domain = self.domain = 'mock'
        self.xform.xmlns = USER_REGISTRATION_XMLNS

    def testCreateBasicWebUser(self):
        """
        test that a basic couch user gets created when calling CouchUser.from_web_user
        """
        username = "joe"
        email = "joe@domain.com"
        password = "password"
        domain = "test"
        couch_user = WebUser.create(domain, username, password, email)

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
        couch_user = WebUser.create(None, username, password, email)
        self.assertEqual(couch_user.username, username)
        self.assertEqual(couch_user.email, email)
        couch_user.add_domain_membership('domain1')
        self.assertEqual(couch_user.domain_memberships[0].domain, 'domain1')
        couch_user.add_domain_membership('domain2')
        self.assertEqual(couch_user.domain_memberships[1].domain, 'domain2')
        django_user = couch_user.get_django_user()
        self.assertEqual(couch_user.user_id, CouchUser.from_django_user(django_user).user_id)

    def _runCreateUserFromRegistrationTest(self):
        """
        test creating of couch user from a registration xmlns.
        this is more of an integration test than a unit test.
        """
        couch_user, created = CommCareUser.create_or_update_from_xform(self.xform)
        self.assertEqual(couch_user.user_id, self.uuid)
        # czue: removed lxml reference
        # uuid = ET.fromstring(xml).findtext(".//{http://openrosa.org/user/registration}uuid")
        couch_user = CommCareUser.get_by_user_id(self.xform.form['uuid'])

        self.assertNotEqual(couch_user, None)
        self.assertEqual(couch_user.username, format_username(self.username, self.domain))
        self.assertEqual(couch_user.domain, self.domain)
        self.assertEqual(couch_user.user_id, self.uuid)
        date = iso_string_to_date(self.date_string)
        self.assertEqual(couch_user.created_on, force_to_datetime(date))
        self.assertEqual(couch_user.device_ids[0], self.registering_device_id)

        django_user = couch_user.get_django_user()
        self.assertEqual(couch_user.user_id, CouchUser.from_django_user(django_user).user_id)

    def testCreateUserFromRegistration(self):
        self._runCreateUserFromRegistrationTest()

    def testCreateUserFromOldRegistration(self):
        self.xform.xmlns = USER_REGISTRATION_XMLNS_DEPRECATED
        self._runCreateUserFromRegistrationTest()

    def testCreateDuplicateUsersFromRegistration(self):
        """
        use case: chw on phone registers a username/password/domain triple somewhere
        another chw somewhere else somehow registers the same username/password/domain triple
        outcome: 2 distinct users on hq with the same info, but the usernames should be
        updated appropriately to not be duplicates.
        """
        first_user, created = CommCareUser.create_or_update_from_xform(self.xform)
        # switch uuid so that we don't violate unique key constraints on django use creation
        xform = self.xform
        xform.form['uuid'] = 'AVNSDNVLDSFDESFSNSIDNFLDKN'
        second_user, created = CommCareUser.create_or_update_from_xform(xform)
        # make sure they got different usernames
        self.assertEqual("test_reg", first_user.username.split("@")[0])
        self.assertEqual("test_reg2", second_user.username.split("@")[0])

    def testEditUserFromRegistration(self):
        """
        Edit a user via registration XML
        """
        # really this should be in the "update" test but all the infrastructure
        # for dealing with the xml payload is here.
        original_user, created = CommCareUser.create_or_update_from_xform(self.xform)
        self.assertTrue(created)
        self.assertEqual("test_reg", original_user.username.split("@")[0])
        original_django_user = original_user.get_django_user()
        original_count = User.objects.count()

        xform = self.xform
        xform.form['username'] = 'a_new_username'
        xform.form['password'] = "foobar"
        self.xform.form['registering_phone_id'] = 'phone_edit'
        xform.form['user_data'] = {'data': [{'@key': 'user_type', '#text': 'boss'}]}
        updated_user, created = CommCareUser.create_or_update_from_xform(xform)
        self.assertFalse(created)
        # make sure they got different usernames
        self.assertEqual("a_new_username", updated_user.username.split("@")[0])
        self.assertEqual("phone_edit", updated_user.device_id)
        self.assertEqual("boss", updated_user.user_data["user_type"])

        # make sure we didn't create a new django user and updated
        # the old one correctly
        updated_django_user = updated_user.get_django_user()
        self.assertEqual(original_count, User.objects.count())
        self.assertEqual(original_django_user.pk, updated_django_user.pk)
        self.assertNotEqual(original_django_user.username, updated_django_user.username)
        self.assertNotEqual(original_django_user.password, updated_django_user.password)

    def testEditUserFromRegistrationWithConflicts(self):
        original_user, created = CommCareUser.create_or_update_from_xform(self.xform)
        self.assertEqual("test_reg", original_user.username.split("@")[0])
        xform = self.xform

        xform.form['uuid'] = 'AVNSDNVLDSFDESFSNSIDNFLDKN'
        xform.form['username'] = 'new_user'
        second_user, created = CommCareUser.create_or_update_from_xform(xform)

        # try to set it to a conflict
        xform.form['username'] = 'test_reg'
        updated_user, created = CommCareUser.create_or_update_from_xform(xform)

        # make sure they got different usernames
        self.assertEqual(second_user.get_id, updated_user.get_id)
        self.assertEqual("test_reg", original_user.username.split("@")[0])
        self.assertEqual("test_reg2", updated_user.username.split("@")[0])

        # since we changed it we should be able to back to the original id
        xform.form['username'] = 'new_user'
        updated_user, created = CommCareUser.create_or_update_from_xform(xform)
        self.assertEqual(second_user.get_id, updated_user.get_id)
        self.assertEqual("new_user", updated_user.username.split("@")[0])


class TestDomainMemberships(TestCase):
    domain = "test-domain"

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete()
        cls.webuser2.delete()
        cls.project.delete()

    @classmethod
    def setUpClass(cls):
        w_username = "joe"
        w_email = "joe@domain.com"
        w2_username = "ben"
        w2_email = "ben@domain.com"
        cc_username = "mobby"
        password = "password"
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
