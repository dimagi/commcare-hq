from django.test import TestCase
from corehq.apps.tzmigration import get_migration_complete, \
    get_migration_status, set_migration_complete
from corehq.apps.tzmigration.api import set_migration_started
from corehq.apps.tzmigration.models import MigrationStatus


class TimezoneMigrationProgressTest(TestCase):
    def test_not_started(self):
        self.assertFalse(get_migration_complete('red'))
        self.assertEqual(get_migration_status('red'),
                         MigrationStatus.NOT_STARTED)

    def test_in_progress(self):
        set_migration_started('yellow')
        self.assertFalse(get_migration_complete('yellow'))
        self.assertEqual(get_migration_status('yellow'),
                         MigrationStatus.IN_PROGRESS)

    def test_complete(self):
        set_migration_complete('green')
        self.assertEqual(get_migration_status('green'),
                         MigrationStatus.COMPLETE)
        self.assertTrue(get_migration_complete('green'))
