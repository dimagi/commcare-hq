from __future__ import absolute_import
from __future__ import unicode_literals
from memoized import Memoized
from django.test import TestCase, SimpleTestCase
import mock
from corehq.apps.export.views.utils import user_can_view_deid_exports
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import Permissions, WebUser, UserRole, DomainMembership
from corehq.apps.users.permissions import DEID_EXPORT_PERMISSION


class PermissionsTest(TestCase):

    def test_OR(self):
        p1 = Permissions(
            edit_web_users=True,
            view_web_users=True,
            view_roles=True,
            view_reports=True,
            view_report_list=['report1'],
        )
        p2 = Permissions(
            edit_apps=True,
            view_reports=True,
            view_report_list=['report2'],
        )
        self.assertEqual(p1 | p2, Permissions(
            edit_apps=True,
            edit_web_users=True,
            view_web_users=True,
            view_roles=True,
            view_reports=True,
            view_report_list=['report1', 'report2'],
        ))


@mock.patch('corehq.apps.export.views.utils.domain_has_privilege',
            lambda domain, privilege: True)
class ExportPermissionsTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(ExportPermissionsTest, cls).setUpClass()
        cls.domain = 'export-permissions-test'
        cls.web_user = WebUser(username='temp@example.com', domains=[cls.domain])
        cls.web_user.domain_memberships = [DomainMembership(domain=cls.domain, role_id='MYROLE')]
        cls.permissions = Permissions()

    def setUp(self):
        super(ExportPermissionsTest, self).setUp()
        test_self = self

        def get_role(self):
            return UserRole(
                domain=test_self.domain,
                permissions=test_self.permissions
            )

        patches = [
            mock.patch.object(DomainMembership, 'role', property(get_role)),
            mock.patch.object(Memoized, '__call__',
                              lambda self, *args, **kwargs: self.func(*args, **kwargs))
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.permissions = Permissions()
        super(ExportPermissionsTest, self).tearDown()

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
