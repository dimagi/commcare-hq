import uuid

from django.test import TestCase
from unittest.mock import patch

from corehq.apps.app_manager.models import LinkedApplication
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.updates import update_user_roles
from corehq.apps.linked_domain.util import _clean_json
from corehq.apps.reports.models import TableauServer, TableauVisualization
from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.userreports.util import get_ucr_class_name
from corehq.apps.users.models import HqPermissions, UserRole
from corehq.apps.users.role_utils import UserRolePresets
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
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

    def test_matching_ids_are_overwritten(self):
        upstream_role = self._create_user_role(self.upstream_domain, name='test')
        self._create_user_role(self.downstream_domain, 'conflicting_name', upstream_id=upstream_role.get_id)

        update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertEqual(1, len(roles))
        self.assertIsNotNone(roles.get('test'))

    def test_unsynced_matching_names_raise_an_error(self):
        self._create_user_role(self.upstream_domain, name='test')
        self._create_user_role(self.downstream_domain, name='test', upstream_id=None)

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to push the following custom roles due to matching (same name) unlinked roles in this'
                ' downstream project space: "test". Please edit the roles to resolve the matching or click'
                ' "Push & Overwrite" to overwrite and link the matching ones.'):
            update_user_roles(self.domain_link)

    def test_cannot_sync_name_change_if_name_is_taken(self):
        upstream_role = self._create_user_role(self.upstream_domain, name='new_name')
        self._create_user_role(self.downstream_domain, name='old_name', upstream_id=upstream_role.get_id)
        self._create_user_role(self.downstream_domain, name='new_name', upstream_id=None)

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to push the following custom roles due to matching (same name) unlinked roles in this'
                ' downstream project space: "new_name". Please edit the roles to resolve the matching or click'
                ' "Push & Overwrite" to overwrite and link the matching ones.'):
            update_user_roles(self.domain_link)

    def test_can_overwrite_matching_names(self):
        upstream_permissions = HqPermissions(view_reports=True)
        downstream_permissions = HqPermissions(view_reports=False)

        self._create_user_role(self.upstream_domain, name='test', permissions=upstream_permissions)
        self._create_user_role(self.downstream_domain, name='test',
                               permissions=downstream_permissions, upstream_id=None)

        update_user_roles(self.domain_link, overwrite=True)

        downstream_roles = UserRole.objects.by_domain_and_name(self.downstream_domain, 'test')
        self.assertEqual(len(downstream_roles), 1)
        self.assertEqual(downstream_roles[0].permissions, upstream_permissions)

    # TODO: Determine whether this should be turned into a parameterized test for all built-in roles
    def test_syncing_built_in_roles_turns_them_into_linked_roles(self):
        role_name = UserRolePresets.APP_EDITOR
        built_in_permissions = UserRolePresets.INITIAL_ROLES[role_name]()

        upstream_role = self._create_user_role(self.upstream_domain, name=role_name,
            permissions=built_in_permissions)
        self._create_user_role(self.downstream_domain, name=role_name, permissions=built_in_permissions,
            upstream_id=None)

        update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertEqual(roles[role_name].upstream_id, upstream_role.get_id)

    def test_built_in_roles_raise_conflict_if_upstream_changed(self):
        role_name = UserRolePresets.APP_EDITOR
        built_in_permissions = UserRolePresets.INITIAL_ROLES[role_name]()

        modified_permissions = self._copy_permissions(built_in_permissions)
        modified_permissions.edit_web_users = not built_in_permissions.edit_web_users

        self._create_user_role(self.upstream_domain, name=role_name, permissions=modified_permissions)
        self._create_user_role(self.downstream_domain, name=role_name, permissions=built_in_permissions)

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to push the following default roles due to matching (same name but different permissions)'
                ' unlinked roles in this downstream project space: "App Editor".'
                ' Please edit the roles to resolve the matching or click "Push & Overwrite"'
                ' to overwrite and link the matching ones.'):
            update_user_roles(self.domain_link)

    def test_built_in_roles_raise_conflict_if_downstream_changed(self):
        role_name = UserRolePresets.APP_EDITOR
        built_in_permissions = UserRolePresets.INITIAL_ROLES[role_name]()

        modified_permissions = self._copy_permissions(built_in_permissions)
        modified_permissions.edit_web_users = not built_in_permissions.edit_web_users

        self._create_user_role(self.upstream_domain, name=role_name, permissions=built_in_permissions)
        self._create_user_role(self.downstream_domain, name=role_name, permissions=modified_permissions)

        with self.assertRaises(UnsupportedActionError):
            update_user_roles(self.domain_link)

    def test_built_in_roles_are_linked_if_they_match(self):
        role_name = UserRolePresets.APP_EDITOR
        built_in_permissions = UserRolePresets.INITIAL_ROLES[role_name]()

        # Permissions can differ from the built-in permissions, provided they still match
        modified_permissions = self._copy_permissions(built_in_permissions)
        modified_permissions.edit_web_users = not built_in_permissions.edit_web_users

        upstream_role = self._create_user_role(
            self.upstream_domain, name=role_name, permissions=modified_permissions)
        self._create_user_role(self.downstream_domain, name=role_name, permissions=modified_permissions)

        update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertEqual(roles[role_name].upstream_id, upstream_role.get_id)

    def test_conflicts_are_reported_in_bulk(self):
        self._create_user_role(self.upstream_domain, name='Role1')
        self._create_user_role(self.upstream_domain, name='Role2')

        self._create_user_role(self.downstream_domain, name='Role1')
        self._create_user_role(self.downstream_domain, name='Role2')

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to push the following custom roles due to matching (same name) unlinked roles in this'
                ' downstream project space: "Role1", "Role2". Please edit the roles to resolve the matching or'
                ' click "Push & Overwrite" to overwrite and link the matching ones.'):
            update_user_roles(self.domain_link)

    def test_default_and_custom_errors_are_reported_together(self):
        self._create_user_role(self.upstream_domain, name=UserRolePresets.APP_EDITOR,
                               permissions=HqPermissions(view_reports=True))
        self._create_user_role(self.upstream_domain, name='CustomRole')

        self._create_user_role(self.downstream_domain, name=UserRolePresets.APP_EDITOR,
                               permissions=HqPermissions(view_reports=False))
        self._create_user_role(self.downstream_domain, name='CustomRole')

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to push the following default roles due to matching (same name but different permissions)'
                ' unlinked roles in this downstream project space: "App Editor".'
                ' Please edit the roles to resolve the matching or click "Push & Overwrite"'
                ' to overwrite and link the matching ones.\n'
                'Failed to push the following custom roles due to matching (same name) unlinked roles in this'
                ' downstream project space: "CustomRole". Please edit the roles to resolve the matching or click'
                ' "Push & Overwrite" to overwrite and link the matching ones.'):
            update_user_roles(self.domain_link)

    def test_error_message_indicates_push(self):
        self._create_user_role(self.upstream_domain, name='Test')
        self._create_user_role(self.downstream_domain, name='Test')

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to push the following custom roles due to matching (same name) unlinked roles in this'
                ' downstream project space: "Test". Please edit the roles to resolve the matching or click'
                ' "Push & Overwrite" to overwrite and link the matching ones.'):
            update_user_roles(self.domain_link, is_pull=False)

    def test_error_message_indicates_pull(self):
        self._create_user_role(self.upstream_domain, name='Test')
        self._create_user_role(self.downstream_domain, name='Test')

        with self.assertRaisesMessage(UnsupportedActionError,
                'Failed to sync the following custom roles due to matching (same name) unlinked roles in this'
                ' downstream project space: "Test". Please edit the roles to resolve the matching or click'
                ' "Sync & Overwrite" to overwrite and link the matching ones.'):
            update_user_roles(self.domain_link, is_pull=True)

    @patch('corehq.apps.linked_domain.updates.get_brief_apps_in_domain')
    def test_web_apps_permissions(self, get_brief_apps_in_domain):
        self._create_user_role(self.upstream_domain, name='Linked & unlinked', permissions=HqPermissions(
            edit_data=True,
            edit_reports=True,
            access_web_apps=False,
            web_apps_list=['123', '456']
        ))

        downstream_app = LinkedApplication(
            _id='789', domain=self.upstream_domain, version=1, name='linked-app', upstream_app_id='123'
        )
        get_brief_apps_in_domain.return_value = [downstream_app]

        update_user_roles(self.domain_link)

        role = UserRole.objects.get_by_domain(self.downstream_domain)[0]
        self.assertListEqual(role.permissions.web_apps_list, [downstream_app.id])

    @flag_enabled('EMBEDDED_TABLEAU')
    def test_tableau_report_permission_does_not_raise_error_if_downstream_role_is_newly_created(self):
        """
        Regression test for https://github.com/dimagi/commcare-hq/pull/34536
        """
        server = TableauServer.objects.create(
            domain=self.upstream_domain,
            server_type="server",
            server_name="my_server",
            target_site="my_site",
        )
        upstream_viz = TableauVisualization.objects.create(
            domain=self.upstream_domain,
            server=server,
        )
        self.upstream_tableau_role = UserRole.create(
            self.upstream_domain, "tableau_test", HqPermissions(view_tableau_list=[str(upstream_viz.id)])
        )

        # successful if a ValueError isn't raised
        update_user_roles(self.domain_link)

    @flag_enabled('EMBEDDED_TABLEAU')
    def test_tableau_report_permissions(self):
        server = TableauServer.objects.create(
            domain=self.upstream_domain,
            server_type='server',
            server_name='my_server',
            target_site='my_site',
        )

        upstream_viz_1 = TableauVisualization.objects.create(
            domain=self.upstream_domain,
            server=server,
        )

        upstream_viz_2 = TableauVisualization.objects.create(
            domain=self.upstream_domain,
            server=server,
        )

        downstream_viz_1 = TableauVisualization.objects.create(
            domain=self.downstream_domain,
            upstream_id=upstream_viz_1.id,
            server=server,
        )
        downstream_viz_2 = TableauVisualization.objects.create(
            domain=self.downstream_domain,
            upstream_id=upstream_viz_2.id,
            server=server,
        )
        downstream_viz_3 = TableauVisualization.objects.create(
            domain=self.downstream_domain,
            upstream_id=None,
            server=server,
        )

        self.upstream_tableau_role = UserRole.create(self.upstream_domain,
                                   'tableau_test',
                                   HqPermissions(view_tableau_list=[str(upstream_viz_1.id)]))
        # Downstream role
        UserRole.create(
            self.downstream_domain, 'tableau_test', HqPermissions(
                view_tableau_list=[str(downstream_viz_1.id), str(downstream_viz_2.id), str(downstream_viz_3.id)]),
            upstream_id=self.upstream_tableau_role.get_id
        )

        update_user_roles(self.domain_link)
        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        # viz_1 should be included because it's linked upstream viz was in upstream role's permission list, and
        # viz_3 should be included because it's in the downstream role's permission list and isn't linked upstream
        self.assertListEqual([str(downstream_viz_1.id), str(downstream_viz_3.id)],
                             roles['tableau_test'].permissions.view_tableau_list)

    def test_profile_permissions(self):
        upstream_definition = CustomDataFieldsDefinition(domain=self.upstream_domain,
                                                         field_type=UserFieldsView.field_type)
        upstream_definition.save()
        upstream_profile1 = CustomDataFieldsProfile(
            name='p1',
            fields={},
            definition=upstream_definition,
        )
        upstream_profile1.save()
        upstream_profile2 = CustomDataFieldsProfile(
            name='p2',
            fields={},
            definition=upstream_definition,
        )
        upstream_profile2.save()
        upstream_profile3 = CustomDataFieldsProfile(
            name='p3',
            fields={},
            definition=upstream_definition,
        )
        upstream_profile3.save()
        downstream_definition = CustomDataFieldsDefinition(domain=self.downstream_domain,
                                                           field_type=UserFieldsView.field_type)
        downstream_definition.save()
        downstream_profile1 = CustomDataFieldsProfile(
            name='p1',
            fields={},
            definition=downstream_definition,
            upstream_id=upstream_profile1.id
        )
        downstream_profile1.save()
        downstream_profile2 = CustomDataFieldsProfile(
            name='p2',
            fields={},
            definition=downstream_definition,
        )
        downstream_profile2.save()
        downstream_profile3 = CustomDataFieldsProfile(
            name='p3',
            fields={},
            definition=downstream_definition,
            upstream_id=upstream_profile3.id
        )
        downstream_profile3.save()

        self.upstream_profile_role = UserRole.create(self.upstream_domain,
                                    'profile_test',
                                    HqPermissions(edit_user_profile=False,
                                                  edit_user_profile_list=[str(upstream_profile1.id),
                                                                    str(upstream_profile2.id)]))
        UserRole.create(
            self.downstream_domain, 'profile_test', HqPermissions(edit_user_profile=False,
                edit_user_profile_list=[str(downstream_profile1.id), str(downstream_profile2.id)]),
            upstream_id=self.upstream_profile_role.get_id
        )
        update_user_roles(self.domain_link)
        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertListEqual([str(downstream_profile1.id), str(downstream_profile2.id)],
                             roles['profile_test'].permissions.edit_user_profile_list)

    def test_when_synced_role_with_name_change_conflicts_with_local_role_conflict_is_raised(self):
        renamed_role = self._create_user_role(self.upstream_domain, name='LocalRoleName')
        # The previously synced role
        self._create_user_role(self.downstream_domain, name='SyncedRole', upstream_id=renamed_role.get_id)
        # A local role with a conflicting name
        self._create_user_role(self.downstream_domain, name='LocalRoleName')

        with self.assertRaises(UnsupportedActionError):
            update_user_roles(self.domain_link)

    def test_force_pushing_a_name_change_conflict_appends_an_identifier_to_synced_role(self):
        renamed_role = self._create_user_role(self.upstream_domain, name='LocalRoleName')
        # The previously synced role
        self._create_user_role(self.downstream_domain, name='SyncedRole', upstream_id=renamed_role.get_id)
        # A local role with a conflicting name
        self._create_user_role(self.downstream_domain, name='LocalRoleName')

        update_user_roles(self.domain_link, overwrite=True)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        # Verify that the local role was not linked
        self.assertIsNone(roles['LocalRoleName'].upstream_id)
        # Verify that the synced role was renamed
        self.assertFalse('SyncedRole' in roles.keys())
        updated_role = roles['LocalRoleName(1)']
        self.assertEqual(updated_role.upstream_id, renamed_role.get_id)

    def test_renaming_continues_until_an_avaialable_integer_is_found(self):
        renamed_role = self._create_user_role(self.upstream_domain, name='LocalRoleName')
        self._create_user_role(self.downstream_domain, name='SyncedRole', upstream_id=renamed_role.get_id)
        self._create_user_role(self.downstream_domain, 'LocalRoleName')
        self._create_user_role(self.downstream_domain, 'LocalRoleName(1)')
        self._create_user_role(self.downstream_domain, 'LocalRoleName(2)')

        update_user_roles(self.domain_link, overwrite=True)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        update_role = roles['LocalRoleName(3)']
        self.assertEqual(update_role.upstream_id, renamed_role.get_id)

    def test_errors_prevent_any_successful_updates(self):
        self._create_user_role(self.upstream_domain, name='SuccessRole')
        self._create_user_role(self.upstream_domain, name='ConflictRole')

        self._create_user_role(self.downstream_domain, name='ConflictRole')

        with self.assertRaises(UnsupportedActionError):
            update_user_roles(self.domain_link)

        roles = {r.name: r for r in UserRole.objects.get_by_domain(self.downstream_domain)}
        self.assertFalse('SuccessRole' in roles.keys())
        self.assertIsNone(roles['ConflictRole'].upstream_id)

    def _create_user_role(self, domain, name='test', permissions=None, assignable_by_ids=None, **kwargs):
        if not permissions:
            permissions = HqPermissions(edit_web_users=True, view_locations=True)
        role = UserRole.create(domain, name, permissions, **kwargs)
        if assignable_by_ids:
            role.set_assignable_by(assignable_by_ids)
        return role

    @classmethod
    def _copy_permissions(cls, permissions):
        # A hacky way to clone permissions
        return HqPermissions.from_permission_list(permissions.to_list())


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
