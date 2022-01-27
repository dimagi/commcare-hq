from decimal import Decimal

from django.test import TestCase

from django_prbac.models import Role

from corehq.apps.accounting.management.commands.change_software_plan_version import (
    NewRoleDoesNotExist,
    OldRoleDoesNotExist,
    change_software_plan_version,
)
from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanVersion,
    SoftwareProductRate,
)


class ChangeSoftwarePlanVersionTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ChangeSoftwarePlanVersionTest, cls).setUpClass()
        cls.generic_product_rate = SoftwareProductRate.new_rate('product', Decimal('0.0'))
        cls.generic_product_rate.save()
        cls.old_role = Role(slug='old_role', name='old')
        cls.old_role.save()
        cls.new_role = Role(slug='new_role', name='new')
        cls.new_role.save()

    def test_raises_old_role_does_not_exist(self):
        with self.assertRaises(OldRoleDoesNotExist):
            change_software_plan_version('invalid_role', 'new_role')

    def test_raises_new_role_does_not_exist(self):
        with self.assertRaises(NewRoleDoesNotExist):
            change_software_plan_version('old_role', 'invalid_role')

    def test_upgrades_successfully(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        old_version = SoftwarePlanVersion(role=self.old_role, plan=plan, product_rate=self.generic_product_rate)
        old_version.save()
        self.assertEqual(old_version.version, 1)

        change_software_plan_version('old_role', 'new_role')

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().version, 2)
        self.assertEqual(plan.get_version().role.slug, 'new_role')

    def test_does_not_upgrade_inactive_versions(self):
        active_role = Role(slug='active_role', name='active')
        active_role.save()
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        inactive_version = SoftwarePlanVersion(
            role=self.old_role,
            plan=plan,
            product_rate=self.generic_product_rate,
            is_active=False,
        )
        inactive_version.save()
        active_version = SoftwarePlanVersion(role=active_role, plan=plan, product_rate=self.generic_product_rate)
        active_version.save()

        change_software_plan_version('old_role', 'new_role')

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().version, 2)
        self.assertEqual(plan.get_version().role.slug, 'active_role')

    def test_limit_to_plans(self):
        plan_to_upgrade = SoftwarePlan(name='Upgrade Plan')
        plan_to_upgrade.save()
        plan_to_ignore = SoftwarePlan(name='Do Not Upgrade Plan')
        plan_to_ignore.save()
        old_version1 = SoftwarePlanVersion(
            role=self.old_role,
            plan=plan_to_upgrade,
            product_rate=self.generic_product_rate,
        )
        old_version2 = SoftwarePlanVersion(
            role=self.old_role,
            plan=plan_to_ignore,
            product_rate=self.generic_product_rate,
        )
        old_version1.save()
        old_version2.save()

        change_software_plan_version('old_role', 'new_role', limit_to_plans=['Upgrade Plan'])

        # refetch
        not_upgraded_plan = SoftwarePlan.objects.get(name='Do Not Upgrade Plan')
        upgraded_plan = SoftwarePlan.objects.get(name='Upgrade Plan')
        self.assertEqual(not_upgraded_plan.get_version().version, 1)
        self.assertEqual(not_upgraded_plan.get_version().role.slug, 'old_role')
        self.assertEqual(upgraded_plan.get_version().version, 2)
        self.assertEqual(upgraded_plan.get_version().role.slug, 'new_role')

    def test_dry_run(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        old_version = SoftwarePlanVersion(role=self.old_role, plan=plan, product_rate=self.generic_product_rate)
        old_version.save()
        self.assertEqual(old_version.version, 1)

        change_software_plan_version('old_role', 'new_role', dry_run=True)

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().version, 1)
        self.assertEqual(plan.get_version().role.slug, 'old_role')
