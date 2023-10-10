from corehq.apps.accounting.models import (SoftwarePlan,
                                           SoftwarePlanEdition,
                                           SoftwarePlanVersion,
                                           SoftwarePlanVisibility,
                                           SoftwareProductRate,
                                           )
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from django_prbac.models import Role


class SoftwarePlanVersionTest(BaseAccountingTest):

    def setUp(self):
        # Create 2 software plans with different versions
        software_plan1 = SoftwarePlan.objects.create(
            name="Software Plan 1",
            description="A software plan have two versions",
            edition=SoftwarePlanEdition.ADVANCED,
            visibility=SoftwarePlanVisibility.PUBLIC,
        )
        product_rate1 = SoftwareProductRate.objects.create(
            monthly_fee=1000,
            name="Advanced Product Rate 1"
        )
        self.plan1_version1 = SoftwarePlanVersion.objects.create(
            plan=software_plan1,
            product_rate=product_rate1,
            role=Role.objects.first(),
        )
        product_rate2 = SoftwareProductRate.objects.create(
            monthly_fee=1200,
            name="Advanced Product Rate 2",
        )
        self.plan1_version2 = SoftwarePlanVersion.objects.create(
            plan=software_plan1,
            product_rate=product_rate2,
            role=Role.objects.first(),
        )

        software_plan2 = SoftwarePlan.objects.create(
            name="Software Plan 2",
            description="A software plan have only one version",
            edition=SoftwarePlanEdition.ADVANCED,
            visibility=SoftwarePlanVisibility.PUBLIC,
        )
        self.plan2_version1 = SoftwarePlanVersion.objects.create(
            plan=software_plan2,
            product_rate=product_rate1,
            role=Role.objects.first(),
        )

    def test_get_most_recent_version(self):
        edition = SoftwarePlanEdition.ADVANCED
        visibility = SoftwarePlanVisibility.PUBLIC

        # Get most recent versions
        recent_versions = SoftwarePlanVersion.get_most_recent_version(edition, visibility)

        self.assertIn(self.plan1_version2, recent_versions)
        self.assertIn(self.plan2_version1, recent_versions)
        self.assertNotIn(self.plan1_version1, recent_versions)
