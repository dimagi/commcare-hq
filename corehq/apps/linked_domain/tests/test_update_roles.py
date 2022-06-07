import uuid

from django.test import TestCase
from unittest.mock import patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.updates import update_user_roles
from corehq.apps.linked_domain.util import _clean_json
from corehq.apps.reports.models import TableauServer, TableauVisualization
from corehq.apps.userreports.util import get_ucr_class_name
from corehq.apps.users.models import HqPermissions, UserRole
from corehq.util.test_utils import flag_enabled


class TestUpdateRoles(TestCase):
    def setUp(self):
        super().setUp()
        self.domain_link = DomainLink(master_domain='upstream-domain', linked_domain='downstream-domain')
        self.upstream_domain = self.domain_link.master_domain
        self.downstream_domain = self.domain_link.linked_domain

    def test_update_report_list_preserves_properties(self):
        self._create_user_role(self.upstream_domain, name='test',
            permissions=HqPermissions(
                edit_data=True,
                edit_reports=True,
            ),
            is_non_admin_editable=True
        )

        update_user_roles(self.domain_link)

        synced_role = UserRole.objects.get_by_domain(self.downstream_domain)[0]
        self.assertTrue(synced_role.name, 'test')
        self.assertTrue(synced_role.permissions.edit_data)
        self.assertTrue(synced_role.permissions.edit_reports)
        self.assertTrue(synced_role.is_non_admin_editable)

    def test_viewable_reports_are_preserved(self):
        self._create_user_role(self.upstream_domain, permissions=HqPermissions(
            view_report_list=[get_ucr_class_name('master_report_id')]
        ))

        report_mapping = {'master_report_id': 'linked_report_id'}
        with patch('corehq.apps.linked_domain.updates.get_static_report_mapping', return_value=report_mapping):
            update_user_roles(self.domain_link)

        roles = UserRole.objects.get_by_domain(self.downstream_domain)
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0].permissions.view_report_list, [get_ucr_class_name('linked_report_id')])

    def test_assignable_by_is_preserved(self):
        supervisor_role = self._create_user_role(self.upstream_domain, name='supervisor')
        self._create_user_role(self.upstream_domain, name='managed', assignable_by_ids=[supervisor_role.id])

        update_user_roles(self.domain_link)
        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertEqual(roles['managed'].assignable_by, [roles['supervisor'].get_id])

    def test_matching_names_are_overwritten(self):
        upstream_role = self._create_user_role(self.upstream_domain, name='test')
        self._create_user_role(self.downstream_domain, name='test')

        update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertEqual(1, len(roles))
        self.assertTrue(roles['test'].permissions.edit_web_users)
        self.assertEqual(roles['test'].upstream_id, upstream_role.get_id)

    def test_matching_ids_are_overwritten(self):
        upstream_role = self._create_user_role(self.upstream_domain, name='test')
        self._create_user_role(self.downstream_domain, 'conflicting_name', upstream_id=upstream_role.get_id)

        update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertEqual(1, len(roles))
        self.assertIsNotNone(roles.get('test'))

    def _create_user_role(self, domain, name='test', permissions=None, assignable_by_ids=None, **kwargs):
        if not permissions:
            permissions = HqPermissions(edit_web_users=True, view_locations=True)
        role = UserRole.create(domain, name, permissions, **kwargs)
        if assignable_by_ids:
            role.set_assignable_by(assignable_by_ids)
        return role

    @flag_enabled('EMBEDDED_TABLEAU')
    def test_tableau_report_permissions(self):
        self.assertEqual([], UserRole.objects.get_by_domain(self.linked_domain))

        server = TableauServer.objects.create(
            domain=self.domain,
            server_type='server',
            server_name='my_server',
            target_site='my_site',
        )

        upstream_viz_1 = TableauVisualization.objects.create(
            domain=self.domain,
            server=server,
        )

        upstream_viz_2 = TableauVisualization.objects.create(
            domain=self.domain,
            server=server,
        )

        downstream_viz_1 = TableauVisualization.objects.create(
            domain=self.linked_domain,
            upstream_id=upstream_viz_1.id,
            server=server,
        )
        downstream_viz_2 = TableauVisualization.objects.create(
            domain=self.linked_domain,
            upstream_id=upstream_viz_2.id,
            server=server,
        )
        downstream_viz_3 = TableauVisualization.objects.create(
            domain=self.linked_domain,
            upstream_id=None,
            server=server,
        )

        self.upstream_tableau_role = UserRole.create(self.domain,
                                   'tableau_test',
                                   HqPermissions(view_tableau_list=[str(upstream_viz_1.id)]))
        # Downstream role
        UserRole.create(
            self.linked_domain, 'tableau_test', HqPermissions(
                view_tableau_list=[str(downstream_viz_1.id), str(downstream_viz_2.id), str(downstream_viz_3.id)]),
            upstream_id=self.upstream_tableau_role.get_id
        )

        update_user_roles(self.domain_link)
        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.linked_domain)}
        # viz_1 should be included because it's linked upstream viz was in upstream role's permission list, and
        # viz_3 should be included because it's in the downstream role's permission list and isn't linked upstream
        self.assertListEqual([str(downstream_viz_1.id), str(downstream_viz_3.id)],
                             roles['tableau_test'].permissions.view_tableau_list)


class TestUpdateRolesRemote(TestCase):

    role_json_template = {
        "name": None,
        "permissions": None,
        "default_landing_page": None,
        "is_non_admin_editable": False,
        "assignable_by": [],
        "is_archived": False,
        "upstream_id": None
    }

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
        self.role1 = UserRole.create(
            domain=self.linked_domain,
            name='test',
            permissions=HqPermissions(
                edit_data=True,
                edit_reports=True,
                view_report_list=[
                    'corehq.reports.DynamicReportmaster_report_id'
                ]
            ),
            is_non_admin_editable=True,
            upstream_id=self.upstream_role1_id
        )

        self.other_role = UserRole.create(
            domain=self.linked_domain,
            name='other_test',
            permissions=HqPermissions(
                edit_web_users=True,
                view_locations=True,
            ),
            assignable_by=[self.role1.id],
        )
        self.other_role.save()

    def tearDown(self):
        for role in UserRole.objects.get_by_domain(self.linked_domain):
            role.delete()
        super(TestUpdateRolesRemote, self).tearDown()

    @patch('corehq.apps.linked_domain.updates.remote_get_user_roles')
    def test_update_remote(self, remote_get_user_roles):
        remote_permissions = HqPermissions(
            edit_data=False,
            edit_reports=True,
            view_report_list=['corehq.reports.static_report']
        )
        # sync with existing local role
        remote_role1 = self._make_remote_role_json(
            _id=self.upstream_role1_id,
            name="test",
            permissions=remote_permissions.to_json(),
        )

        # create new role
        remote_role_other = self._make_remote_role_json(
            _id=uuid.uuid4().hex,
            name="another",
            permissions=HqPermissions().to_json(),
            assignable_by=[self.upstream_role1_id]
        )

        remote_get_user_roles.return_value = [
            _clean_json(role) for role in [remote_role1, remote_role_other]
        ]

        update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.linked_domain)}
        self.assertEqual(3, len(roles))
        self.assertEqual(roles['test'].permissions, remote_permissions)
        self.assertEqual(roles['test'].is_non_admin_editable, False)
        self.assertEqual(roles['another'].assignable_by, [self.role1.get_id])
        self.assertEqual(roles['another'].permissions, HqPermissions())
        self.assertEqual(roles['other_test'].assignable_by, [self.role1.get_id])

    def _make_remote_role_json(self, **kwargs):
        role_json = self.role_json_template.copy()
        role_json.update(**kwargs)
        return role_json
