import sys
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.commands import migrate
from django.test import SimpleTestCase

from .. import django_migrations as reindexer


def handle_migrate(*args, **kw):
    reindexer.RequestReindex().run(None, None)


@patch.object(migrate.Command, "handle", handle_migrate)
class TestMigrateWithReindex(SimpleTestCase):

    def test_migrate_does_reindex(self):
        def command(name, *args, **kw):
            log.append(name)

        log = []
        with patch.object(reindexer, "call_command", command):
            call_command("migrate")
        self.assert_reindex_done(log)

    def test_migrate_multi_does_reindex(self):
        def command(name, *args, **kw):
            log.append(name)

        log = []
        with patch.object(reindexer, "call_command", command):
            call_command("migrate_multi")
        self.assert_reindex_done(log)

    def test_migrate_multi_does_reindex_on_migration_error(self):
        def handle_fail(*args, **kw):
            handle_migrate()
            raise Exception("fail")

        def command(name, *args, **kw):
            log.append(name)

        log = []
        stderr = StringIO()
        with (
            patch.object(reindexer, "call_command", command),
            patch.object(migrate.Command, "handle", handle_fail),
            patch.object(sys, "stderr", stderr),
            self.assertRaises(SystemExit),
        ):
            call_command("migrate_multi")
        self.assertIn("Exception: fail", stderr.getvalue())
        self.assert_reindex_done(log)

    def assert_reindex_done(self, log):
        self.assertEqual(log, [
            "preindex_everything",
            "sync_finish_couchdb_hq",
        ])
        self.assertFalse(reindexer.should_reindex)
