from unittest.mock import patch

from django.test import TestCase

from django_prbac.models import Grant, Role

from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    SoftwarePlanVisibility,
    SoftwareProductRate,
)
from corehq.apps.linked_domain.management.commands.migrate_feature_flag_domains import (
    _get_migration_info,
    _get_or_create_new_software_plan,
    _get_or_create_new_software_plan_version,
    _get_or_create_role_with_privilege,
    _should_skip_role,
    _update_roles_in_place,
    _update_versions_in_place,
)


class UpdateRolesInPlaceTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.privilege_role = Role.objects.create(slug='privilege', name='test privilege')

    def test_successful_update(self):
        role = Role.objects.create(slug='role', name='test role')

        _update_roles_in_place([role.slug], self.privilege_role.slug)

        try:
            Grant.objects.get(from_role=role, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {role.slug} and {self.privilege_role.slug}")

    def test_dry_run(self):
        role = Role.objects.create(slug='role', name='test role')

        _update_roles_in_place([role.slug], self.privilege_role.slug, dry_run=True)

        with self.assertRaises(Grant.DoesNotExist):
            Grant.objects.get(from_role=role, to_role=self.privilege_role)

    def test_invalid_role(self):
        with self.assertRaises(Role.DoesNotExist):
            _update_roles_in_place(['unknown-role'], self.privilege_role.slug)

    def test_invalid_privilege_role(self):
        role = Role.objects.create(slug='role', name='test role')

        with self.assertRaises(Role.DoesNotExist):
            _update_roles_in_place([role.slug], 'unknown-role')

    def test_multiple_roles(self):
        role1 = Role.objects.create(slug='role1', name='test role 1')
        role2 = Role.objects.create(slug='role2', name='test role 2')

        _update_roles_in_place([role1.slug, role2.slug], self.privilege_role.slug)

        try:
            Grant.objects.get(from_role=role1, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {role1.slug} and {self.privilege_role.slug}")

        try:
            Grant.objects.get(from_role=role2, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {role2.slug} and {self.privilege_role.slug}")


class GetOrCreateRoleWithPrivilegeTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.privilege_role = Role.objects.create(slug='privilege', name='test privilege')
        self.existing_role = Role.objects.create(slug='role', name='Role')

    def test_returns_none_if_role_exists_but_does_not_have_privilege(self):
        Role.objects.create(slug='role_erm', name='Role (With ERM)')
        # no grant created to add privilege
        role = _get_or_create_role_with_privilege(self.existing_role.slug, self.privilege_role.slug)
        self.assertIsNone(role)

    def test_returns_existing_role_with_privilege(self):
        role_with_privilege = Role.objects.create(slug='role_erm', name='Role (With ERM)')
        Grant.objects.create(from_role=role_with_privilege, to_role=self.privilege_role)

        actual_role = _get_or_create_role_with_privilege(self.existing_role.slug, self.privilege_role.slug)
        self.assertEqual(actual_role.id, role_with_privilege.id)

    def test_returns_new_role(self):
        actual_role = _get_or_create_role_with_privilege(self.existing_role.slug, self.privilege_role.slug)
        self.assertEqual(actual_role.slug, 'role_erm')
        try:
            Grant.objects.get(from_role=actual_role, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {actual_role.slug} and {self.privilege_role.slug}")


class UpdateVersionInPlaceTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.software_plan = SoftwarePlan.objects.create(
            name="Test Software Plan",
            description="Software Plan For Unit Tests",
            edition=SoftwarePlanEdition.PRO,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=False,
        )
        cls.product_rate = SoftwareProductRate.objects.create(monthly_fee=100, name=cls.software_plan.name)

    def setUp(self) -> None:
        super().setUp()
        self.privilege_role = Role.objects.create(slug='privilege', name='test privilege')
        self.existing_role = Role.objects.create(slug='role', name='Role')

    def test_succesful_when_new_role_with_erm_created(self):
        version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )
        _update_versions_in_place([version.id], self.privilege_role.slug)

        # refetch
        updated_version = SoftwarePlanVersion.objects.get(id=version.id)
        self.assertEqual(updated_version.role.slug, 'role_erm')
        try:
            Grant.objects.get(from_role=updated_version.role, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {updated_version.role.slug} and {self.privilege_role.slug}")

    def test_successful_when_role_with_privilege_exists(self):
        role_with_privilege = Role.objects.create(slug='role_erm', name='Role (with ERM)')
        Grant.objects.create(from_role=role_with_privilege, to_role=self.privilege_role)

        version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )
        _update_versions_in_place([version.id], self.privilege_role.slug)

        # refetch
        updated_version = SoftwarePlanVersion.objects.get(id=version.id)
        self.assertEqual(updated_version.role.slug, role_with_privilege.slug)
        try:
            Grant.objects.get(from_role=updated_version.role, to_role=self.privilege_role)
        except Grant.DoesNotExist:
            self.fail(f"Grant not found for {updated_version.role.slug} and {self.privilege_role.slug}")

    def test_fails_if_role_exists_without_grant(self):
        Role.objects.create(slug='role_erm', name='Role (with ERM)')
        # intentionally do not create grant between role with privilege and privilege itself
        version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )

        _update_versions_in_place([version.id], self.privilege_role.slug)

        # refetch
        updated_version = SoftwarePlanVersion.objects.get(id=version.id)
        self.assertEqual(updated_version.role.slug, self.existing_role.slug)
        with self.assertRaises(Grant.DoesNotExist):
            Grant.objects.get(from_role=updated_version.role, to_role=self.privilege_role)

    def test_dry_run(self):
        version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )
        _update_versions_in_place([version.id], self.privilege_role.slug, dry_run=True)

        # refetch
        updated_version = SoftwarePlanVersion.objects.get(id=version.id)
        self.assertEqual(updated_version.role.slug, self.existing_role.slug)
        with self.assertRaises(Grant.DoesNotExist):
            Grant.objects.get(from_role=updated_version.role, to_role=self.privilege_role)


class GetOrCreateNewSoftwarePlanTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.software_plan = SoftwarePlan.objects.create(
            name="Test Software Plan",
            description="Software Plan For Unit Tests",
            edition=SoftwarePlanEdition.PRO,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=False,
            is_annual_plan=True,
            max_domains=3,
        )

    def test_new_plan_created(self):
        new_plan = _get_or_create_new_software_plan(self.software_plan)
        self.assertEqual(new_plan.name, "Test Software Plan (With ERM)")
        self.assertEqual(new_plan.description, self.software_plan.description)
        self.assertEqual(new_plan.edition, self.software_plan.edition)
        self.assertEqual(new_plan.visibility, self.software_plan.visibility)
        self.assertEqual(new_plan.is_customer_software_plan, self.software_plan.is_customer_software_plan)
        self.assertEqual(new_plan.max_domains, self.software_plan.max_domains)
        self.assertEqual(new_plan.is_annual_plan, self.software_plan.is_annual_plan)

    def test_existing_plan_returned_if_exists(self):
        expected_software_plan = SoftwarePlan.objects.create(
            name="Test Software Plan (With ERM)",
            description="Software Plan For Unit Tests",
            edition=SoftwarePlanEdition.PRO,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=False,
            is_annual_plan=True,
            max_domains=3,
        )
        new_plan = _get_or_create_new_software_plan(self.software_plan)

        self.assertEqual(new_plan.name, expected_software_plan.name)
        self.assertEqual(new_plan.id, expected_software_plan.id)


class GetOrCreateNewSoftwarePlanVersionTest(TestCase):

    def setUp(self):
        super().setUp()
        self.software_plan = SoftwarePlan.objects.create(
            name="Test Software Plan",
            description="Software Plan For Unit Tests",
            edition=SoftwarePlanEdition.PRO,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=False,
        )
        self.product_rate = SoftwareProductRate.objects.create(monthly_fee=100, name=self.software_plan.name)
        self.existing_role = Role.objects.create(slug='existing_role', name='Existing Role')
        self.new_role = Role.objects.create(slug='new_role', name='New Role')
        self.software_plan_version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )

    def test_new_version_referencing_new_role(self):
        version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )

        new_version = _get_or_create_new_software_plan_version(self.software_plan, version, self.new_role)

        # refetch
        updated_version = SoftwarePlanVersion.objects.get(id=new_version.id)
        self.assertEqual(self.software_plan.get_version(), updated_version)
        with self.assertRaises(Grant.DoesNotExist):
            Grant.objects.get(from_role=updated_version.role, to_role=self.new_role)

    def test_existing_version_returned(self):
        expected_version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.new_role,
        )
        new_version = _get_or_create_new_software_plan_version(
            self.software_plan, self.software_plan_version, self.new_role
        )

        self.assertEqual(expected_version.role.slug, new_version.role.slug)
        self.assertEqual(expected_version.id, new_version.id)

    def test_dry_run_does_not_make_changes(self):
        new_version = _get_or_create_new_software_plan_version(
            self.software_plan, self.software_plan_version, self.new_role, dry_run=True
        )

        self.assertIsNone(new_version.id)
        self.assertEqual(self.software_plan.get_version(), self.software_plan_version)


class ShouldSkipRoleTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.privilege_role = Role.objects.create(slug='privilege', name='test privilege')
        self.role_to_check = Role.objects.create(slug='role', name='Role')

    def test_returns_false(self):
        result = _should_skip_role(self.role_to_check, self.privilege_role)
        self.assertFalse(result)

    def test_returns_true_if_grant_exists(self):
        Grant.objects.create(from_role=self.role_to_check, to_role=self.privilege_role)
        result = _should_skip_role(self.role_to_check, self.privilege_role)
        self.assertTrue(result)

    def test_returns_true_if_role_to_skip_is_supplied(self):
        result = _should_skip_role(self.role_to_check, self.privilege_role, roles_to_skip=['role'])
        self.assertTrue(result)

    def test_returns_false_if_role_to_skip_is_not_supplied(self):
        result = _should_skip_role(self.role_to_check, self.privilege_role, roles_to_skip=['role-to-skip'])
        self.assertFalse(result)


class GetMigrationInfoTests(TestCase):
    """
    Mainly trying to ensure that these 3 cases are true:
    # 1) a role can be directly updated (create a Grant) if all domains referencing this role have toggle enabled
    # For both 2 and 3, a new role must be created
    # 2) software plan versions can be directly updated (update role ref) if all domains referencing the software
    plan have toggles enabled
    # 3) a new software plan version must be created to the appropriate subscriptions updated to reference the new
    version
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.software_plan = SoftwarePlan.objects.create(
            name="Test Software Plan",
            description="Software Plan For Unit Tests",
            edition=SoftwarePlanEdition.PRO,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=False,
        )
        cls.product_rate = SoftwareProductRate.objects.create(monthly_fee=100, name=cls.software_plan.name)
        cls.setUpPatchers()

    @classmethod
    def setUpPatchers(cls):
        domains_for_version_patcher = patch(
            'corehq.apps.linked_domain.management.commands.migrate_feature_flag_domains._get_domains_for_version'
        )
        cls.mock_get_domains_for_version = domains_for_version_patcher.start()
        cls.addClassCleanup(domains_for_version_patcher.stop)

        domains_for_versions_patcher = patch(
            'corehq.apps.linked_domain.management.commands.migrate_feature_flag_domains._get_domains_for_versions'
        )
        cls.mock_get_domains_for_versions = domains_for_versions_patcher.start()
        cls.addClassCleanup(domains_for_versions_patcher.stop)

        all_domains_patcher = patch(
            'corehq.apps.linked_domain.management.commands.migrate_feature_flag_domains'
            '._all_domains_use_linked_domains')
        cls.mock_all_domains_use_linked_domains = all_domains_patcher.start()
        cls.mock_all_domains_use_linked_domains.return_value = True
        cls.addClassCleanup(all_domains_patcher.stop)

        get_domains_patcher = patch(
            'corehq.apps.linked_domain.management.commands.migrate_feature_flag_domains'
            '._get_domains_that_use_linked_domains')
        cls.mock_domains_that_use_linked_domains = get_domains_patcher.start()
        cls.addClassCleanup(get_domains_patcher.stop)

    def setUp(self) -> None:
        super().setUp()
        self.privilege_role = Role.objects.create(slug='privilege', name='test privilege')
        self.existing_role = Role.objects.create(slug='role', name='Role')

    def test_returns_roles_to_update(self):
        # all domains for all plans that reference this role have feature flag enabled
        SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )
        self.mock_get_domains_for_versions.return_value = ['domain']
        self.mock_all_domains_use_linked_domains.return_value = True

        roles_to_update, version_to_update, versions_to_increment = _get_migration_info(
            [self.existing_role], self.privilege_role.slug
        )

        self.assertEqual(roles_to_update, ['role'])
        self.assertFalse(version_to_update)
        self.assertFalse(versions_to_increment)

    def test_returns_nothing_if_role_should_be_skipped(self):
        # all domains for all plans that reference this role have feature flag enabled
        SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )
        role_to_skip1, created1 = Role.objects.get_or_create(slug='enterprise_plan_v0')
        role_to_skip2, created2 = Role.objects.get_or_create(slug='enterprise_plan_v1')

        roles_to_update, version_to_update, versions_to_increment = _get_migration_info(
            [role_to_skip1, role_to_skip2], self.privilege_role.slug
        )

        self.assertFalse(roles_to_update)
        self.assertFalse(version_to_update)
        self.assertFalse(versions_to_increment)

    def test_returns_plan_versions_to_update(self):
        # all domains for all plans that reference this role have feature flag enabled
        version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )

        def toggle_handler(domains):
            return 'disabled-domain' not in domains

        self.mock_all_domains_use_linked_domains.side_effect = toggle_handler
        self.mock_get_domains_for_versions.return_value = ['domain', 'disabled-domain']
        self.mock_get_domains_for_version.return_value = ['domain']

        roles_to_update, version_to_update, versions_to_increment = _get_migration_info(
            [self.existing_role], self.privilege_role.slug
        )

        self.assertFalse(roles_to_update)
        self.assertEqual(version_to_update, [version.id])
        self.assertFalse(versions_to_increment)

    def test_returns_plan_versions_to_increment(self):
        # all domains for all plans that reference this role have feature flag enabled
        version = SoftwarePlanVersion.objects.create(
            plan=self.software_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )

        self.mock_all_domains_use_linked_domains.return_value = False
        self.mock_get_domains_for_versions.return_value = ['domain', 'disabled-domain']
        self.mock_get_domains_for_version.return_value = ['domain', 'disabled-domain']
        self.mock_domains_that_use_linked_domains.return_value = ['domain']

        roles_to_update, version_to_update, versions_to_increment = _get_migration_info(
            [self.existing_role], self.privilege_role.slug
        )

        self.assertFalse(roles_to_update)
        self.assertFalse(version_to_update)
        self.assertEqual(versions_to_increment, {version.id: ['domain']})

    def test_role_is_not_updated_directly_for_public_plans(self):
        public_plan = SoftwarePlan.objects.create(
            name="Test Public Software Plan",
            description="Public Software Plan For Unit Tests",
            edition=SoftwarePlanEdition.PRO,
            visibility=SoftwarePlanVisibility.PUBLIC,
            is_customer_software_plan=False,
        )
        version = SoftwarePlanVersion.objects.create(
            plan=public_plan,
            product_rate=self.product_rate,
            role=self.existing_role,
        )
        self.mock_get_domains_for_versions.return_value = ['domain']
        self.mock_all_domains_use_linked_domains.return_value = True

        roles_to_update, version_to_update, versions_to_increment = _get_migration_info(
            [self.existing_role], self.privilege_role.slug
        )

        self.assertFalse(roles_to_update)
        self.assertEqual(version_to_update, [version.id])
        self.assertFalse(versions_to_increment)
