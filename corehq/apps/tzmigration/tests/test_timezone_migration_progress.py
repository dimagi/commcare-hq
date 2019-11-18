from django.test import TestCase

from corehq.apps.domain_migration_flags.models import MigrationStatus
from corehq.apps.tzmigration.api import (
    get_tz_migration_complete,
    get_tz_migration_status,
    set_tz_migration_complete,
    set_tz_migration_not_started,
    set_tz_migration_started,
)


class TimezoneMigrationProgressTest(TestCase):

    def test_not_started(self):
        self.assertFalse(get_tz_migration_complete('red'))
        self.assertEqual(get_tz_migration_status('red'),
                         MigrationStatus.NOT_STARTED)

    def test_in_progress(self):
        set_tz_migration_started('yellow')
        self.assertFalse(get_tz_migration_complete('yellow'))
        self.assertEqual(get_tz_migration_status('yellow'),
                         MigrationStatus.IN_PROGRESS)

    def test_complete(self):
        set_tz_migration_complete('green')
        self.assertEqual(get_tz_migration_status('green'),
                         MigrationStatus.COMPLETE)
        self.assertTrue(get_tz_migration_complete('green'))

    def test_abort(self):
        set_tz_migration_started('yellow')
        self.assertFalse(get_tz_migration_complete('yellow'))
        self.assertEqual(get_tz_migration_status('yellow'),
                         MigrationStatus.IN_PROGRESS)
        set_tz_migration_not_started('yellow')
        self.assertFalse(get_tz_migration_complete('yellow'))
        self.assertEqual(get_tz_migration_status('yellow'),
                         MigrationStatus.NOT_STARTED)
