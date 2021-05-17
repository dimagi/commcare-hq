from mock import patch

from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_user_roles
from corehq.apps.userreports.util import get_ucr_class_name
from corehq.apps.users.models import Permissions, SQLUserRole


class TestUpdateRoles(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super(TestUpdateRoles, cls).setUpClass()
        cls.linked_app.save()

        permissions = Permissions(
            edit_data=True,
            edit_reports=True,
            view_report_list=[
                'corehq.reports.DynamicReportmaster_report_id'
            ]
        )
        cls.role = SQLUserRole.create(cls.domain, 'test', permissions, is_non_admin_editable=True)
        cls.other_role = SQLUserRole.create(
            cls.domain, 'other_test', Permissions(edit_web_users=True, view_locations=True)
        )
        cls.other_role.set_assignable_by([cls.role.id])

    @classmethod
    def tearDownClass(cls):
        cls.role.delete()
        cls.other_role.delete()
        super(TestUpdateRoles, cls).tearDownClass()

    def tearDown(self):
        for role in SQLUserRole.objects.by_domain(self.linked_domain):
            role.delete()
        super(TestUpdateRoles, self).tearDown()

    def test_update_report_list(self):
        self.assertEqual([], SQLUserRole.objects.by_domain(self.linked_domain))

        report_mapping = {'master_report_id': 'linked_report_id'}
        with patch('corehq.apps.linked_domain.updates.get_static_report_mapping', return_value=report_mapping):
            update_user_roles(self.domain_link)

        roles = {r.name: r for r in SQLUserRole.objects.by_domain(self.linked_domain)}
        self.assertEqual(2, len(roles))
        self.assertEqual(roles['test'].permissions.view_report_list, [get_ucr_class_name('linked_report_id')])
        self.assertTrue(roles['test'].is_non_admin_editable)

        self.assertTrue(roles['other_test'].permissions.edit_web_users)
        self.assertEqual(roles['other_test'].assignable_by, [roles['test'].id])

    def test_match_names(self):
        self.assertEqual([], SQLUserRole.objects.by_domain(self.linked_domain))

        # create role in linked domain
        SQLUserRole.create(
            self.linked_domain, 'other_test', Permissions(edit_web_users=True, view_locations=True)
        )

        update_user_roles(self.domain_link)
        roles = {r.name: r for r in SQLUserRole.objects.by_domain(self.linked_domain)}
        self.assertEqual(2, len(roles))
        self.assertTrue(roles['other_test'].permissions.edit_web_users)
        self.assertEqual(roles['other_test'].upstream_id, self.other_role.id)

    def test_match_ids(self):
        self.assertEqual([], SQLUserRole.objects.by_domain(self.linked_domain))

        # create role in linked domain
        SQLUserRole.create(
            self.linked_domain, 'id_test', Permissions(edit_web_users=True, view_locations=True),
            upstream_id=self.other_role.id
        )

        update_user_roles(self.domain_link)
        roles = {r.name: r for r in SQLUserRole.objects.by_domain(self.linked_domain)}
        self.assertEqual(2, len(roles), roles.keys())
        self.assertIsNotNone(roles.get('other_test'))
        self.assertTrue(roles['other_test'].permissions.edit_web_users)
        self.assertEqual(roles['other_test'].upstream_id, self.other_role.id)
