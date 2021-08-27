from couchdbkit.ext.django.schema import ListProperty
from django.test import SimpleTestCase

import mock
from testil import eq, assert_raises

from corehq.apps.export.views.utils import user_can_view_deid_exports
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import (
    DomainMembership,
    Permissions,
    WebUser, PARAMETERIZED_PERMISSIONS, PermissionInfo,
)
from corehq.apps.users.permissions import DEID_EXPORT_PERMISSION, has_permission_to_view_report, \
    ODATA_FEED_PERMISSION


@mock.patch('corehq.apps.export.views.utils.domain_has_privilege',
            lambda domain, privilege: True)
class PermissionsHelpersTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(PermissionsHelpersTest, cls).setUpClass()
        cls.domain = 'export-permissions-test'
        cls.admin_domain = 'export-permissions-test-admin'
        cls.web_user = WebUser(username='temp@example.com', domains=[cls.domain, cls.admin_domain])
        cls.web_user.domain_memberships = [
            DomainMembership(domain=cls.domain, role_id='MYROLE'),
            DomainMembership(domain=cls.admin_domain, is_admin=True)
        ]
        cls.permissions = Permissions()

    def setUp(self):
        super(PermissionsHelpersTest, self).setUp()
        test_self = self

        def get_role(self, domain=None):
            return mock.Mock(
                domain=test_self.domain,
                permissions=test_self.permissions,
                spec=["domain", "permissions"]
            )

        assert hasattr(WebUser.has_permission, "get_cache"), "not memoized?"
        patches = [
            mock.patch.object(DomainMembership, 'role', property(get_role)),
            mock.patch.object(WebUser, 'get_role', get_role),
            mock.patch.object(WebUser, 'has_permission', WebUser.has_permission.__wrapped__),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.permissions = Permissions()
        super(PermissionsHelpersTest, self).tearDown()

    def test_deid_permission(self):
        self.assertFalse(user_can_view_deid_exports(self.domain, self.web_user))
        self.permissions = Permissions(view_report_list=[DEID_EXPORT_PERMISSION])
        self.assertTrue(
            self.permissions.has(get_permission_name(Permissions.view_report),
                                 data=DEID_EXPORT_PERMISSION))
        self.assertTrue(
            self.web_user.has_permission(
                self.domain, get_permission_name(Permissions.view_report),
                data=DEID_EXPORT_PERMISSION)
        )

        self.assertTrue(user_can_view_deid_exports(self.domain, self.web_user))

    def test_view_reports(self):
        self.assertFalse(self.web_user.can_view_reports(self.domain))
        self.permissions = Permissions(view_reports=True)
        self.assertTrue(self.web_user.can_view_reports(self.domain))

    def test_has_permission_to_view_report_all(self):
        self.assertFalse(has_permission_to_view_report(self.web_user, self.domain, ODATA_FEED_PERMISSION))
        self.permissions = Permissions(view_reports=True)
        self.assertTrue(has_permission_to_view_report(self.web_user, self.domain, ODATA_FEED_PERMISSION))

    def test_has_permission_to_view_report(self):
        self.assertFalse(has_permission_to_view_report(self.web_user, self.domain, ODATA_FEED_PERMISSION))
        self.permissions = Permissions(view_report_list=[ODATA_FEED_PERMISSION])
        self.assertTrue(has_permission_to_view_report(self.web_user, self.domain, ODATA_FEED_PERMISSION))


def test_parameterized_permission_covers_all():
    list_names = set(PARAMETERIZED_PERMISSIONS.values())
    list_properties = {
        name for name, type_ in Permissions.properties().items()
        if isinstance(type_, ListProperty)
    }
    eq(list_names, list_properties)

    parameterized_perms = set(PARAMETERIZED_PERMISSIONS.keys())
    eq(set(), parameterized_perms - set(Permissions.properties()))


def test_parameterized_permission_validation():
    # no exception raised
    PermissionInfo(Permissions.view_apps.name, allow=PermissionInfo.ALLOW_ALL)
    with assert_raises(TypeError):
        PermissionInfo(Permissions.view_apps.name, allow=["app1"])
