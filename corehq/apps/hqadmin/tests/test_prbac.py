# Use modern Python

# Django imports
from django.test import TestCase

# External imports
from django_prbac.models import Grant, Role

# CCHQ imports
from corehq.apps.hqadmin.management.commands import cchq_prbac_bootstrap


class TestCchqPrbacBootstrap(TestCase):
    """
    Tests the PRBAC bootstrap with and without --dry-run
    """

    @classmethod
    def setUpClass(cls):
        super(TestCchqPrbacBootstrap, cls).setUpClass()
        Grant.objects.all().delete()
        Role.objects.all().delete()

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
