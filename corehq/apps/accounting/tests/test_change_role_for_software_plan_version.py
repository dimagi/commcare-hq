from decimal import Decimal

from django.test import TestCase

from django_prbac.models import Role

from corehq.apps.accounting.management.commands.change_role_for_software_plan_version import (
    change_role_for_software_plan_version,
    NewRoleDoesNotExist,
    OldRoleDoesNotExist,
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

    def test_successful_change(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        version = SoftwarePlanVersion(role=self.old_role, plan=plan, product_rate=self.generic_product_rate)
        version.save()
        self.assertEqual(version.version, 1)

        change_role_for_software_plan_version('old_role', 'new_role')

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().version, 1)
        self.assertEqual(plan.get_version().role.slug, 'new_role')

    def test_does_not_change_inactive_versions(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        inactive_version = SoftwarePlanVersion(
            role=self.old_role,
            plan=plan,
            product_rate=self.generic_product_rate,
            is_active=False,
        )
        inactive_version.save()

        active_role = Role.objects.create(slug='active_role', name='active')
        active_version = SoftwarePlanVersion(role=active_role, plan=plan, product_rate=self.generic_product_rate)
        active_version.save()

        change_role_for_software_plan_version('old_role', 'new_role')

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().version, 2)
        self.assertEqual(plan.get_version().role.slug, 'active_role')

    def test_dry_run(self):
        plan = SoftwarePlan(name='Test Plan')
        plan.save()
        version = SoftwarePlanVersion(role=self.old_role, plan=plan, product_rate=self.generic_product_rate)
        version.save()

        change_role_for_software_plan_version('old_role', 'new_role', dry_run=True)

        # refetch
        plan = SoftwarePlan.objects.get(name='Test Plan')
        self.assertEqual(plan.get_version().role.slug, 'old_role')
