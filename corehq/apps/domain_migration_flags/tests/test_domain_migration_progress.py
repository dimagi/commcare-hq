import uuid
from datetime import datetime
from unittest.mock import Mock

from django.test import TestCase

from corehq.apps.domain_migration_flags.api import (
    ALL_DOMAINS,
    any_migrations_in_progress,
    get_migration_complete,
    get_migration_status,
    migration_in_progress,
    once_off_migration,
    set_migration_complete,
    set_migration_not_started,
    set_migration_started,
)
from corehq.apps.domain_migration_flags.models import (
    DomainMigrationProgress,
    MigrationStatus,
)


class DomainMigrationProgressTest(TestCase):

    def setUp(self):
        self.slug = uuid.uuid4().hex

    def get_progress(self, domain):
        return DomainMigrationProgress.objects.get(domain=domain, migration_slug=self.slug)

    def test_not_started(self):
        self.assertFalse(get_migration_complete('red', self.slug))
        self.assertEqual(get_migration_status('red', self.slug),
                         MigrationStatus.NOT_STARTED)

    def test_in_progress(self):
        set_migration_started('yellow', self.slug)
        self.assertFalse(get_migration_complete('yellow', self.slug))
        self.assertTrue(migration_in_progress('yellow', self.slug))
        self.assertTrue(migration_in_progress('yellow', self.slug, True))
        self.assertEqual(get_migration_status('yellow', self.slug),
                         MigrationStatus.IN_PROGRESS)
        self.assertEqual(get_migration_status('yellow', 'otherslug'),
                         MigrationStatus.NOT_STARTED)

        progress = self.get_progress('yellow')
        self.assertIsNotNone(progress.started_on)
        self.assertLessEqual(progress.started_on, datetime.utcnow())

    def test_dry_run(self):
        set_migration_started('yellow', self.slug, dry_run=True)
        self.assertFalse(get_migration_complete('yellow', self.slug))
        self.assertFalse(migration_in_progress('yellow', self.slug))
        self.assertTrue(migration_in_progress('yellow', self.slug, True))
        self.assertEqual(get_migration_status('yellow', self.slug),
                         MigrationStatus.DRY_RUN)
        self.assertEqual(get_migration_status('yellow', 'otherslug'),
                         MigrationStatus.NOT_STARTED)

        progress = self.get_progress('yellow')
        self.assertIsNotNone(progress.started_on)
        self.assertLessEqual(progress.started_on, datetime.utcnow())

    def test_continue_live_migration(self):
        set_migration_started('yellow', self.slug, dry_run=True)
        self.assertFalse(migration_in_progress('yellow', self.slug))
        self.assertTrue(migration_in_progress('yellow', self.slug, include_dry_runs=True))
        # Live migration finishes ... and is continued later
        set_migration_started('yellow', self.slug, dry_run=True)
        self.assertFalse(migration_in_progress('yellow', self.slug))
        self.assertTrue(migration_in_progress('yellow', self.slug, include_dry_runs=True))

    def test_migration_after_live_migration(self):
        set_migration_started('yellow', self.slug, dry_run=True)
        self.assertFalse(migration_in_progress('yellow', self.slug))
        self.assertTrue(migration_in_progress('yellow', self.slug, include_dry_runs=True))
        # Live migration finishes ... and is completed with normal migration
        set_migration_started('yellow', self.slug)
        self.assertTrue(migration_in_progress('yellow', self.slug))

    def test_complete(self):
        set_migration_complete('green', self.slug)
        self.assertEqual(get_migration_status('green', self.slug),
                         MigrationStatus.COMPLETE)
        self.assertTrue(get_migration_complete('green', self.slug))
        self.assertFalse(get_migration_complete('green', 'otherslug'))

        progress = self.get_progress('green')
        self.assertIsNotNone(progress.completed_on)
        self.assertLessEqual(progress.completed_on, datetime.utcnow())

    def test_abort(self):
        set_migration_started('yellow', self.slug)
        self.assertFalse(get_migration_complete('yellow', self.slug))
        self.assertEqual(get_migration_status('yellow', self.slug),
                         MigrationStatus.IN_PROGRESS)
        set_migration_not_started('yellow', self.slug)
        self.assertFalse(get_migration_complete('yellow', self.slug))
        self.assertEqual(get_migration_status('yellow', self.slug),
                         MigrationStatus.NOT_STARTED)
        self.assertIsNone(self.get_progress('yellow').started_on)

    def test_any_migrations_in_progress(self):
        self.assertFalse(any_migrations_in_progress('purple'))
        set_migration_started('purple', self.slug)
        self.assertTrue(any_migrations_in_progress('purple'))
        set_migration_started('purple', 'other_slug')
        set_migration_not_started('purple', self.slug)
        self.assertTrue(any_migrations_in_progress('purple'))
        set_migration_complete('purple', 'other_slug')
        self.assertFalse(any_migrations_in_progress('purple'))

    def test_once_off_decorator(self):
        actual_migration = Mock()

        @once_off_migration(self.slug)
        def basic_migration():
            self.assertEqual(get_migration_status(ALL_DOMAINS, self.slug), MigrationStatus.IN_PROGRESS)
            actual_migration()

        self.assertEqual(get_migration_status(ALL_DOMAINS, self.slug), MigrationStatus.NOT_STARTED)
        actual_migration.assert_not_called()

        basic_migration()
        self.assertEqual(get_migration_status(ALL_DOMAINS, self.slug), MigrationStatus.COMPLETE)
        actual_migration.assert_called_once()

        basic_migration()
        actual_migration.assert_called_once()

    def test_once_off_decorator_failure(self):
        actual_migration = Mock()

        @once_off_migration(self.slug)
        def failing_migration():
            self.assertEqual(get_migration_status(ALL_DOMAINS, self.slug), MigrationStatus.IN_PROGRESS)
            actual_migration()
            raise ValueError('this migration failed')

        self.assertEqual(get_migration_status(ALL_DOMAINS, self.slug), MigrationStatus.NOT_STARTED)
        self.assertEqual(actual_migration.call_count, 0)

        with self.assertRaises(ValueError):
            failing_migration()
        self.assertEqual(get_migration_status(ALL_DOMAINS, self.slug), MigrationStatus.NOT_STARTED)
        self.assertEqual(actual_migration.call_count, 1)

        with self.assertRaises(ValueError):
            failing_migration()
        self.assertEqual(actual_migration.call_count, 2)
