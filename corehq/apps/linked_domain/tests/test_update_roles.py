from mock import patch

from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_user_roles
from corehq.apps.userreports.util import get_ucr_class_name
from corehq.apps.users.models import Permissions, UserRole


class TestUpdateRoles(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super(TestUpdateRoles, cls).setUpClass()
        cls.linked_app.save()

        cls.role = UserRole(
            domain=cls.domain,
            name='test',
            permissions=Permissions(
                edit_data=True,
                edit_reports=True,
                view_report_list=[
                    'corehq.reports.DynamicReportmaster_report_id'
                ]
            ),
            is_non_admin_editable=True,
        )
        cls.role.save()

        cls.other_role = UserRole(
            domain=cls.domain,
            name='other_test',
            permissions=Permissions(
                edit_web_users=True,
                view_locations=True,
            ),
            assignable_by=[cls.role.get_id],
        )
        cls.other_role.save()

    @classmethod
    def tearDownClass(cls):
        cls.role.delete()
        cls.other_role.delete()
        super(TestUpdateRoles, cls).tearDownClass()

    def tearDown(self):
        for role in UserRole.by_domain(self.linked_domain):
            role.delete()
        super(TestUpdateRoles, self).tearDown()

    def test_update_report_list(self):
        self.assertEqual([], UserRole.by_domain(self.linked_domain))

        report_mapping = {'master_report_id': 'linked_report_id'}
        with patch('corehq.apps.linked_domain.updates.get_static_report_mapping', return_value=report_mapping):
            update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.by_domain(self.linked_domain)}
        self.assertEqual(2, len(roles))
        self.assertEqual(roles['test'].permissions.view_report_list, [get_ucr_class_name('linked_report_id')])
        self.assertTrue(roles['test'].is_non_admin_editable)

        self.assertTrue(roles['other_test'].permissions.edit_web_users)
        self.assertEqual(roles['other_test'].assignable_by, [roles['test'].get_id])
