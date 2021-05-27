import uuid

from django.test import TestCase
from mock import patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_user_roles
from corehq.apps.linked_domain.util import _clean_json
from corehq.apps.userreports.util import get_ucr_class_name
from corehq.apps.users.models import Permissions, UserRole


class TestUpdateRoles(BaseLinkedAppsTest):
    @classmethod
    def setUpClass(cls):
        super(TestUpdateRoles, cls).setUpClass()
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

    def test_match_names(self):
        self.assertEqual([], UserRole.by_domain(self.linked_domain))

        role = UserRole(
            domain=self.linked_domain,
            name='other_test',
            permissions=Permissions(
                edit_web_users=False,
                view_locations=True,
            ),
            assignable_by=[self.role.get_id],
        )
        role.save()

        update_user_roles(self.domain_link)
        roles = {r.name: r for r in UserRole.by_domain(self.linked_domain)}
        self.assertEqual(2, len(roles))
        self.assertTrue(roles['other_test'].permissions.edit_web_users)
        self.assertEqual(roles['other_test'].upstream_id, self.other_role.get_id)

    def test_match_ids(self):
        self.assertEqual([], UserRole.by_domain(self.linked_domain))

        role = UserRole(
            domain=self.linked_domain,
            name='id_test',
            permissions=Permissions(
                edit_web_users=False,
                view_locations=True,
            ),
            assignable_by=[self.role.get_id],
            upstream_id=self.other_role.get_id
        )
        role.save()

        update_user_roles(self.domain_link)
        roles = {r.name: r for r in UserRole.by_domain(self.linked_domain)}
        self.assertEqual(2, len(roles))
        self.assertIsNotNone(roles.get('other_test'))
        self.assertTrue(roles['other_test'].permissions.edit_web_users)
        self.assertEqual(roles['other_test'].upstream_id, self.other_role.get_id)


class TestUpdateRolesRemote(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestUpdateRolesRemote, cls).setUpClass()
        cls.domain_obj = create_domain('domain')
        cls.domain = cls.domain_obj.name

        cls.linked_domain_obj = create_domain('domain-2')
        cls.linked_domain = cls.linked_domain_obj.name

        cls.domain_link = DomainLink.link_domains(cls.linked_domain, cls.domain)
        cls.domain_link.remote_base_url = "http://other.org"
        cls.domain_link.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_link.delete()
        cls.domain_obj.delete()
        cls.linked_domain_obj.delete()
        super(TestUpdateRolesRemote, cls).tearDownClass()

    def setUp(self):
        self.upstream_role1_id = uuid.uuid4().hex
        self.role1 = UserRole(
            domain=self.linked_domain,
            name='test',
            permissions=Permissions(
                edit_data=True,
                edit_reports=True,
                view_report_list=[
                    'corehq.reports.DynamicReportmaster_report_id'
                ]
            ),
            is_non_admin_editable=True,
            upstream_id=self.upstream_role1_id
        )
        self.role1.save()

        self.other_role = UserRole(
            domain=self.linked_domain,
            name='other_test',
            permissions=Permissions(
                edit_web_users=True,
                view_locations=True,
            ),
            assignable_by=[self.role1.get_id],
        )
        self.other_role.save()

    def tearDown(self):
        for role in UserRole.by_domain(self.linked_domain):
            role.delete()
        super(TestUpdateRolesRemote, self).tearDown()

    @patch('corehq.apps.linked_domain.updates.remote_get_user_roles')
    def test_update_remote(self, remote_get_user_roles):
        remote_permissions = Permissions(
            edit_data=False,
            edit_reports=True,
            view_report_list=['corehq.reports.static_report']
        )
        # sync with existing local role
        remote_role1 = UserRole(
            _id=self.upstream_role1_id,
            name='test',
            permissions=remote_permissions,
            is_non_admin_editable=False
        )
        # create new role
        remote_role_other = UserRole(
            _id=uuid.uuid4().hex,
            name="another",
            permissions=Permissions(),
            assignable_by=[self.upstream_role1_id]
        )
        remote_get_user_roles.return_value = [
            _clean_json(role.to_json()) for role in [remote_role1, remote_role_other]
        ]

        update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.by_domain(self.linked_domain)}
        self.assertEqual(3, len(roles))
        self.assertEqual(roles['test'].permissions, remote_permissions)
        self.assertEqual(roles['test'].is_non_admin_editable, False)
        self.assertEqual(roles['another'].assignable_by, [self.role1.get_id])
        self.assertEqual(roles['another'].permissions, Permissions())
        self.assertEqual(roles['other_test'].assignable_by, [self.role1.get_id])
