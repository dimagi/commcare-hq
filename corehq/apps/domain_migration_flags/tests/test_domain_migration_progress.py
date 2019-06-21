from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from datetime import datetime

from django.test import TestCase

from corehq.apps.domain_migration_flags.api import (
    any_migrations_in_progress,
    get_migration_complete,
    get_migration_status,
    migration_in_progress,
    set_migration_complete,
    set_migration_not_started,
    set_migration_started,
)
from corehq.apps.domain_migration_flags.models import (
    DomainMigrationProgress,
    MigrationStatus,
)


class DomainMigrationProgressTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DomainMigrationProgressTest, cls).setUpClass()
        cls.slug = uuid.uuid4().hex

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
