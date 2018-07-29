from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import TestCase

from corehq.apps.domain_migration_flags.api import (
    get_migration_complete,
    get_migration_status,
    set_migration_complete,
    set_migration_not_started,
    set_migration_started,
    any_migrations_in_progress)
from corehq.apps.domain_migration_flags.models import MigrationStatus


class DomainMigrationProgressTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DomainMigrationProgressTest, cls).setUpClass()
        cls.slug = uuid.uuid4().hex

    def test_not_started(self):
        self.assertFalse(get_migration_complete('red', self.slug))
        self.assertEqual(get_migration_status('red', self.slug),
                         MigrationStatus.NOT_STARTED)

    def test_in_progress(self):
        set_migration_started('yellow', self.slug)
        self.assertFalse(get_migration_complete('yellow', self.slug))
        self.assertEqual(get_migration_status('yellow', self.slug),
                         MigrationStatus.IN_PROGRESS)
        self.assertEqual(get_migration_status('yellow', 'otherslug'),
                         MigrationStatus.NOT_STARTED)

    def test_complete(self):
        set_migration_complete('green', self.slug)
        self.assertEqual(get_migration_status('green', self.slug),
                         MigrationStatus.COMPLETE)
        self.assertTrue(get_migration_complete('green', self.slug))
        self.assertFalse(get_migration_complete('green', 'otherslug'))

    def test_abort(self):
        set_migration_started('yellow', self.slug)
        self.assertFalse(get_migration_complete('yellow', self.slug))
        self.assertEqual(get_migration_status('yellow', self.slug),
                         MigrationStatus.IN_PROGRESS)
        set_migration_not_started('yellow', self.slug)
        self.assertFalse(get_migration_complete('yellow', self.slug))
        self.assertEqual(get_migration_status('yellow', self.slug),
                         MigrationStatus.NOT_STARTED)

    def test_any_migrations_in_progress(self):
        self.assertFalse(any_migrations_in_progress('purple'))
        set_migration_started('purple', self.slug)
        self.assertTrue(any_migrations_in_progress('purple'))
        set_migration_started('purple', 'other_slug')
        set_migration_not_started('purple', self.slug)
        self.assertTrue(any_migrations_in_progress('purple'))
        set_migration_complete('purple', 'other_slug')
        self.assertFalse(any_migrations_in_progress('purple'))
