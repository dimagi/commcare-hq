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
            )
        )
        cls.role.save()

    @classmethod
    def tearDownClass(cls):
        cls.role.delete()
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

        roles = UserRole.by_domain(self.linked_domain)
        self.assertEqual(1, len(roles))
        self.assertEqual(roles[0].permissions.view_report_list, [get_ucr_class_name('linked_report_id')])
