from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_user_roles
from corehq.apps.users.models import UserRole, Permissions


class TestUpdateRoles(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super(TestUpdateRoles, cls).setUpClass()
        cls.linked_app.master = cls.plain_master_app.get_id
        cls.linked_app.save()

        cls.role = UserRole(
            domain=cls.domain,
            name='test',
            permissions=Permissions(
                edit_data=True,
                view_web_apps_list=[
                    cls.plain_master_app.get_id
                ]
            )
        )
        cls.role.save()

    @classmethod
    def tearDownClass(cls):
        cls.role.delete()
        super(TestUpdateRoles, cls).tearDownClass()

    def test_update_web_apps_list(self):
        self.assertEqual([], UserRole.by_domain(self.linked_domain))
        update_user_roles(self.domain_link)

        roles = UserRole.by_domain(self.linked_domain)
        self.assertEqual(1, len(roles))
        self.assertEqual(roles[0].permissions.view_web_apps_list, [self.linked_app._id])


