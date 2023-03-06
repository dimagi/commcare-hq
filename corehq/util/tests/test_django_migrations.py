from io import StringIO
from unittest.mock import patch

from django.core.management.commands import makemigrations
from django.db.migrations.operations import RunPython
from django.test import TestCase

from corehq.preindex import apps as preindex

from ..django_migrations import patch_migration_autodetector


class TestMigrationAutodetector(TestCase):

    def test_patch_migration_autodetector(self):
        def autodetect_migrations(self, add_operation):
            log.append("detect")
            add_operation(self.label, operation)
            return lambda: log.append("write extra")

        def command_writer(self_, changes):
            log.append("write changes")
            migrations = changes.get("preindex", [])
            operations = [o for m in migrations for o in m.operations]
            self.assertIn(operation, operations, changes)

        log = []
        operation = RunPython(RunPython.noop, RunPython.noop)
        output = StringIO()
        command = makemigrations.Command(output, output)
        with (
            patch.object(preindex.Config, "autodetect_migrations", new=autodetect_migrations),
            patch.object(makemigrations.Command, "write_migration_files", new=command_writer),
            patch_migration_autodetector(command),
        ):
            command.run_from_argv(["manage.py", "makemigrations", "preindex"])

        self.assertEqual(log, ["detect", "write changes", "write extra"])
        self.assertEqual(output.getvalue(), "")
