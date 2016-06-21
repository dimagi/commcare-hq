# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Django imports
from django.test import TestCase

# External imports
from django.core.management import call_command
from django_prbac.models import Grant, Role

# CCHQ imports
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    Feature,
    FeatureRate,
    SoftwarePlan,
    SoftwarePlanVersion,
    SoftwareProduct,
    SoftwareProductRate,
)
from corehq.apps.hqadmin.management.commands import cchq_prbac_bootstrap


class TestCchqPrbacBootstrap(TestCase):
    """
    Tests the PRBAC bootstrap with and without --dry-run
    """

    @classmethod
    def setUpClass(cls):
        Grant.objects.all().delete()
        Role.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        # re-bootstrap for other tests
        call_command('cchq_prbac_bootstrap', testing=True)

        DefaultProductPlan.objects.all().delete()
        SoftwarePlanVersion.objects.all().delete()
        SoftwarePlan.objects.all().delete()
        SoftwareProductRate.objects.all().delete()
        SoftwareProduct.objects.all().delete()
        FeatureRate.objects.all().delete()
        Feature.objects.all().delete()
        call_command('cchq_software_plan_bootstrap', testing=True)

    def test_dry_run(self):
        """
        When --dry-run is passed, no models should be created
        """
        self.assertEquals(Role.objects.count(), 0)
        self.assertEquals(Grant.objects.count(), 0)

        command = cchq_prbac_bootstrap.Command()
        command.handle(dry_run=True)

        self.assertEquals(Role.objects.count(), 0)
        self.assertEquals(Grant.objects.count(), 0)

    def test_non_dry_run(self):
        """
        When there is no --dry-run passed, it defaults to false, and
        things happen. Furthermore, the thing should be idempotent
        """
        self.assertEquals(Role.objects.count(), 0)
        self.assertEquals(Grant.objects.count(), 0)

        command = cchq_prbac_bootstrap.Command()
        command.handle(dry_run=False)

        # Just make sure something happened
        self.assertGreater(Role.objects.count(), 10)
        self.assertGreater(Grant.objects.count(), 10)

        role_count = Role.objects.count()
        grant_count = Grant.objects.count()

        command.handle(dry_run=False)

        self.assertEquals(Role.objects.count(), role_count)
        self.assertEquals(Grant.objects.count(), grant_count)
