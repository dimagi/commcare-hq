from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    SoftwarePlanVisibility,
    SoftwareProductRate,
)
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from django_prbac.models import Role
import random


class SoftwarePlanVersionTest(BaseAccountingTest):

    def setUp(self):
        self.edition = SoftwarePlanEdition.ADVANCED
        self.visibility = SoftwarePlanVisibility.PUBLIC
        # Create 2 software plans
        self.software_plan1 = SoftwarePlan.objects.create(
            name="Software Plan 1",
            description="A software plan have two versions",
            edition=self.edition,
            visibility=self.visibility,
        )
        self.software_plan2 = SoftwarePlan.objects.create(
            name="Software Plan 2",
            description="A software plan have only one version",
            edition=self.edition,
            visibility=self.visibility,
        )

    def test_get_most_recent_version_is_most_recent(self):
        plan1_old = _create_plan_version(self.software_plan1)
        plan1_new = _create_plan_version(self.software_plan1)
        plan2 = _create_plan_version(self.software_plan2)

        # Get most recent versions
        recent_versions = SoftwarePlanVersion.get_most_recent_version(self.edition, self.visibility)

        self.assertIn(plan1_new, recent_versions)
        self.assertIn(plan2, recent_versions)
        self.assertNotIn(plan1_old, recent_versions)


def _create_plan_version(software_plan):
    product_rate = SoftwareProductRate.objects.create(
        monthly_fee=random.randint(1, 5000), name="Product Rate")
    return SoftwarePlanVersion.objects.create(
        plan=software_plan,
        product_rate=product_rate,
        role=Role.objects.first(),
    )
