from decimal import Decimal

from django.test import TestCase

from django_prbac.models import Role

from corehq.apps.accounting.management.commands.change_role_for_software_plan_version import (
    NewRoleDoesNotExist,
    OldRoleDoesNotExist,
    PlanVersionAndRoleMismatch,
    change_role_for_software_plan_version,
)
from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanVersion,
    SoftwareProductRate,
)


class ChangeRoleForSoftwarePlanVersionTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ChangeRoleForSoftwarePlanVersionTest, cls).setUpClass()
        cls.generic_product_rate = SoftwareProductRate.new_rate('product', Decimal('0.0'))
        cls.generic_product_rate.save()
        cls.old_role = Role(slug='old_role', name='old')
        cls.old_role.save()
        cls.new_role = Role(slug='new_role', name='new')
        cls.new_role.save()

    def test_raises_old_role_does_not_exist(self):
        with self.assertRaises(OldRoleDoesNotExist):
            change_role_for_software_plan_version('invalid_role', 'new_role')

    def test_raises_new_role_does_not_exist(self):
        with self.assertRaises(NewRoleDoesNotExist):
            change_role_for_software_plan_version('old_role', 'invalid_role')

    def test_changes_active_versions(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        active_version = SoftwarePlanVersion(
            role=self.old_role,
            plan=plan,
            product_rate=self.generic_product_rate,
            is_active=True
        )
        active_version.save()
        self.assertEqual(active_version.version, 1)

        change_role_for_software_plan_version('old_role', 'new_role')

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().version, 1)
        self.assertEqual(plan.get_version().role.slug, 'new_role')

    def test_changes_inactive_versions(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        inactive_version = SoftwarePlanVersion(
            role=self.old_role,
            plan=plan,
            product_rate=self.generic_product_rate,
            is_active=False,
        )
        inactive_version.save()
        self.assertEqual(inactive_version.version, 1)

        active_role = Role.objects.create(slug='active_role', name='active')
        active_version = SoftwarePlanVersion(role=active_role, plan=plan, product_rate=self.generic_product_rate)
        active_version.save()

        change_role_for_software_plan_version('old_role', 'new_role')

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        # ensure software plan's active version is still the active role
        self.assertEqual(plan.get_version().role.slug, 'active_role')
        inactive_version = plan.softwareplanversion_set.filter(is_active=False).latest('date_created')
        # ensure the inactive plan version was updated to the new role
        self.assertEqual(inactive_version.role.slug, 'new_role')

    def test_dry_run(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        version = SoftwarePlanVersion(role=self.old_role, plan=plan, product_rate=self.generic_product_rate)
        version.save()

        change_role_for_software_plan_version('old_role', 'new_role', dry_run=True)

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().role.slug, 'old_role')

    def test_limit_to_plan_version_id(self):
        plan_to_update = SoftwarePlan(name='Plan To Update')
        plan_to_update.save()
        version_to_update = SoftwarePlanVersion(
            role=self.old_role, plan=plan_to_update, product_rate=self.generic_product_rate
        )
        version_to_update.save()

        plan_to_ignore = SoftwarePlan(name='Plan To Ignore')
        plan_to_ignore.save()
        version_to_ignore = SoftwarePlanVersion(
            role=self.old_role, plan=plan_to_ignore, product_rate=self.generic_product_rate
        )
        version_to_ignore.save()

        change_role_for_software_plan_version(
            'old_role', 'new_role', limit_to_plan_version_id=version_to_update.id
        )

        # refetch
        plan_to_update = SoftwarePlan.objects.get(name='Plan To Update')
        plan_to_ignore = SoftwarePlan.objects.get(name='Plan To Ignore')
        self.assertEqual(plan_to_update.get_version().role.slug, 'new_role')
        self.assertEqual(plan_to_ignore.get_version().role.slug, 'old_role')

    def test_raises_exception_if_plan_version_id_does_not_reference_old_role(self):
        plan = SoftwarePlan(name='Test Plan 1')
        plan.save()
        version = SoftwarePlanVersion(role=self.old_role, plan=plan, product_rate=self.generic_product_rate)
        version.save()
        Role.objects.create(slug='mismatch_role', name='mismatch')

        with self.assertRaises(PlanVersionAndRoleMismatch):
            change_role_for_software_plan_version('mismatch_role', 'new_role', limit_to_plan_version_id=version.id)
