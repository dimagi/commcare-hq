from unittest.mock import patch

from decorator import contextmanager
from django.test import TestCase
from django.utils.functional import classproperty

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser, DomainMembershipError, HqPermissions
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.role_utils import UserRolePresets


class BaseAuthorizationTest(TestCase):

    @classproperty
    def __test__(cls):
        return cls is not BaseAuthorizationTest

    @classmethod
    def setUpTestData(cls):
        cls.domain = 'my-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.user = cls._create_user(cls.domain)
        cls.test_role = UserRole.create(cls.domain, 'test role', permissions=HqPermissions(
            edit_web_users=True
        ))
        cls.mobile_worker_default_role = UserRole.create(
            cls.domain,
            UserRolePresets.MOBILE_WORKER,
            is_commcare_user_default=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(None, None)
        # to circumvent domain.delete()'s recursive deletion that this test doesn't need
        Domain.get_db().delete_doc(cls.domain_obj)
        super().tearDownClass()

    def setUp(self):
        self.user.has_permission.reset_cache(self.user)
        try:
            self.user.is_domain_admin.reset_cache(self.user)
        except AttributeError:
            pass

    @contextmanager
    def _set_role(self, domain, user, is_admin=False):
        role = 'admin' if is_admin else self.test_role.get_qualified_id()
        user.set_role(domain, role)
        yield
        user.set_role(domain, 'none')

    @classmethod
    def _create_user(cls, domain):
        raise NotImplementedError()

    # ----------------------------------------
    # get_membership

    def test_get_membership(self):
        dm = self.user.get_domain_membership(self.domain)
        self.assertEqual(dm.domain, self.domain)

    def test_get_membership__no_membership(self):
        self.assertIsNone(self.user.get_domain_membership('other'))

    def test_get_membership__null_domain(self):
        self.assertIsNone(self.user.get_domain_membership(None))

    # ----------------------------------------
    # get_role

    def test_get_role(self):
        with self._set_role(self.domain, self.user):
            role = self.user.get_role(self.domain)
            self.assertEqual(role.name, 'test role')

    def test_get_role__not_set(self):
        self.assertIsNone(self.user.get_role(self.domain))

    def test_get_role__no_membership(self):
        with self.assertRaises(DomainMembershipError):
            self.user.get_role('other')

    def test_get_role__null_domain(self):
        with self.assertRaises(DomainMembershipError):
            self.user.get_role(None)

    # --------------------------------------------
    # is_domain_admin

    def test_is_domain_admin__admin_role(self):
        with self._set_role(self.domain, self.user, is_admin=True):
            self.assertTrue(self.user.is_domain_admin(self.domain))

    def test_is_domain_admin__non_admin_role(self):
        with self._set_role(self.domain, self.user):
            self.assertFalse(self.user.is_domain_admin(self.domain))

    def test_is_domain_admin__no_role(self):
        self.assertFalse(self.user.is_domain_admin(self.domain))

    def test_is_domain_admin__no_membership(self):
        self.assertFalse(self.user.is_domain_admin('other'))

    def test_is_domain_admin__null_domain(self):
        self.assertFalse(self.user.is_domain_admin(None))

    # --------------------------------------------
    # is_member_of

    def test_is_member_of(self):
        self.assertTrue(self.user.is_member_of(self.domain))

    def test_is_member_of__no_membership(self):
        self.assertFalse(self.user.is_member_of('other'))

    def test_is_member_of__null_domain(self):
        self.assertFalse(self.user.is_member_of(None))

    # --------------------------------------------
    # has_permission

    def test_has_permission__from_role(self):
        with self._set_role(self.domain, self.user):
            self.assertTrue(self.user.has_permission(self.domain, 'edit_web_users'))

    def test_has_permission__admin(self):
        with self._set_role(self.domain, self.user, is_admin=True):
            self.assertTrue(self.user.has_permission(self.domain, 'edit_web_users'))

    def test_has_permission__default_yes(self):
        self.assertTrue(self.user.has_permission(self.domain, 'report_an_issue'))

    def test_has_permission__default_no(self):
        self.assertFalse(self.user.has_permission(self.domain, 'edit_web_users'))

    def test_has_permission__default_yes__no_membership(self):
        self.assertFalse(self.user.has_permission('other', 'report_an_issue'))

    def test_has_permission__default_yes__null_domain(self):
        self.assertFalse(self.user.has_permission(None, 'report_an_issue'))


class TestMobileUserAuthorizationFunctions(BaseAuthorizationTest):
    @classmethod
    def _create_user(cls, domain):
        return CommCareUser.create(
            domain=domain,
            username='birdman',
            password='***',
            created_by=None,
            created_via=None,
        )

    def test_get_role__not_set(self):
        """Mobile workers have a default role"""
        role = self.user.get_role(self.domain)
        self.assertEqual(role.name, UserRolePresets.MOBILE_WORKER)

    def test_is_domain_admin__admin_role(self):
        with self._set_role(self.domain, self.user, is_admin=True):
            # mobile user can never be a domain admin
            self.assertFalse(self.user.is_domain_admin(self.domain))


class TestWebUserAuthorizationFunctions(BaseAuthorizationTest):
    @classmethod
    def _create_user(cls, domain):
        return WebUser.create(
            username='billy@goats.com',
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )


class TestSuperUserAuthorizationFunctions(BaseAuthorizationTest):
    @classmethod
    def _create_user(cls, domain):
        user = WebUser.create(
            username='super@goats.com',
            domain=cls.domain,
            password='***',
            created_by=None,
            created_via=None,
        )
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return user

    def test_get_role(self):
        with self._set_role(self.domain, self.user):
            role = self.user.get_role(self.domain)
            self.assertEqual(role.name, "Admin")  # admin even though role isn't

    def test_get_role__not_set(self):
        role = self.user.get_role(self.domain)
        self.assertEqual(role.name, "Admin")

    def test_get_role__no_membership(self):
        role = self.user.get_role('other')
        self.assertEqual(role.name, "Admin")

    def test_get_role__null_domain(self):
        # TODO should this be None?
        role = self.user.get_role(None)
        self.assertEqual(role.name, "Admin")

    def test_get_role___not_set__no_checking_global_admin(self):
        self.assertIsNone(self.user.get_role(self.domain, checking_global_admin=False))

    @patch('corehq.apps.users.models.domain_restricts_superusers', return_value=True)
    def test_get_role___not_set__domain_restricts_superusers(self, _mock):
        # TODO: should this be None?
        role = self.user.get_role(self.domain)
        self.assertEqual(role.name, "Admin")

    @patch('corehq.apps.users.models.domain_restricts_superusers', return_value=True)
    def test_get_role__domain_restricts_superusers(self, _mock):
        with self._set_role(self.domain, self.user):
            role = self.user.get_role(self.domain)
            # TODO: should this be 'test role'?
            self.assertEqual(role.name, "Admin")

    def test_get_role__no_membership__no_checking_global_admin(self):
        with self.assertRaises(DomainMembershipError):
            self.user.get_role('other', checking_global_admin=False)

    @patch('corehq.apps.users.models.domain_restricts_superusers', return_value=True)
    def test_get_role__no_membership__domain_restricts_superusers(self, _mock):
        # TODO: should this raise a DM exception?
        role = self.user.get_role('other')
        self.assertEqual(role.name, "Admin")

    # --------------------------------------------
    # super user is_domain_admin

    def test_is_domain_admin__non_admin_role(self):
        with self._set_role(self.domain, self.user):
            self.assertTrue(self.user.is_domain_admin(self.domain))  # true even though role is not

    def test_is_domain_admin__no_role(self):
        self.assertTrue(self.user.is_domain_admin(self.domain))

    def test_is_domain_admin__no_membership(self):
        self.assertTrue(self.user.is_domain_admin('other'))

    @patch('corehq.apps.users.models.domain_restricts_superusers', return_value=True)
    def test_is_domain_admin__non_admin_role__domain_restricts_superusers(self, _mock):
        with self._set_role(self.domain, self.user):
            self.assertFalse(self.user.is_domain_admin(self.domain))

    # --------------------------------------------
    # is_member_of

    def test_is_member_of__no_membership(self):
        self.assertTrue(self.user.is_member_of('other'))

    @patch('corehq.apps.users.models.domain_restricts_superusers', return_value=True)
    def test_is_member_of__no_membership__domain_restricts_superusers(self, _mock):
        self.assertFalse(self.user.is_member_of('other'))

    # --------------------------------------------
    # has_permission

    def test_has_permission__default_no(self):
        self.assertTrue(self.user.has_permission(self.domain, 'edit_web_users'))

    def test_has_permission__default_yes__no_membership(self):
        self.assertTrue(self.user.has_permission('other', 'report_an_issue'))

    def test_has_permission__default_yes__null_domain(self):
        self.assertTrue(self.user.has_permission(None, 'report_an_issue'))

    @patch('corehq.apps.users.models.domain_restricts_superusers', return_value=True)
    def test_has_permission__default_no__domain_restricts_superusers(self, _mock):
        self.assertFalse(self.user.has_permission(self.domain, 'edit_web_users'))

    @patch('corehq.apps.users.models.domain_restricts_superusers', return_value=True)
    def test_has_permission__default_yes__no_membership__domain_restricts_superusers(self, _mock):
        self.assertFalse(self.user.has_permission('other', 'report_an_issue'))
