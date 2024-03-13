import re
from argparse import ArgumentTypeError
from datetime import datetime
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from corehq.apps.es import cases, case_search, groups
from corehq.apps.es.management.commands.make_elastic_migration import Command
from corehq.apps.es.migration_operations import (
    CreateIndex,
    DeleteIndex,
    UpdateIndexMapping,
)
from corehq.apps.es.tests.utils import es_test


class mock_datetime:

    _now = datetime(2022, 12, 28, 13, 25, 42, 999999)

    @classmethod
    def utcnow(cls):
        return cls._now


@es_test
class TestMakeElasticMigrationCommand(TestCase):

    @patch("corehq.apps.es.management.commands.make_elastic_migration.datetime", mock_datetime)
    def test_build_migration_create_index(self):

        def test_changes(self_, changes):
            migration, = changes.pop(Command.DJANGO_APP_LABEL)
            operation, = migration.operations
            self.assertEqual({}, changes)
            self.assertIsInstance(operation, CreateIndex)
            self.assertEqual("groups-20221228", operation.name)
            self.assertEqual([5, 6], operation.es_versions)

        with patch.object(Command, "write_migration_files", test_changes):
            call_command("make_elastic_migration", "-c", "groups", "-t", 5, "-t", 6)

    def test_build_migration_delete_index(self):

        def test_changes(self_, changes):
            migration, = changes.pop(Command.DJANGO_APP_LABEL)
            operation, = migration.operations
            self.assertEqual({}, changes)
            self.assertIsInstance(operation, DeleteIndex)
            self.assertEqual(index_name, operation.name)

        index_name = "trashme"
        with patch.object(Command, "write_migration_files", test_changes):
            call_command("make_elastic_migration", "-d", index_name)

    def test_build_migration_update_index_mapping(self):

        def test_changes(self_, changes):
            migration, = changes.pop(Command.DJANGO_APP_LABEL)
            operation, = migration.operations
            self.assertEqual({}, changes)
            self.assertIsInstance(operation, UpdateIndexMapping)
            self.assertEqual(groups.group_adapter.index_name, operation.name)
            self.assertEqual(["domain", "name"], sorted(operation.properties))

        with patch.object(Command, "write_migration_files", test_changes):
            call_command("make_elastic_migration", "-u", "groups:name,domain")

    @patch("corehq.apps.es.management.commands.make_elastic_migration.datetime", mock_datetime)
    def test_build_migration_multi_operation(self):

        def test_changes(self_, changes):
            migration, = changes.pop(Command.DJANGO_APP_LABEL)
            self.assertEqual({}, changes)
            operations = sorted(migration.operations, key=sort_ops)
            create_1, create_2, delete_1, delete_2, update_1, update_2 = operations
            self.assertEqual(create_1.name, "groups-20221228")
            self.assertEqual(create_2.name, "sms-custom")
            self.assertEqual(delete_1.name, "trashme_1")
            self.assertEqual(delete_2.name, "trashme_2")
            self.assertEqual(update_1.name, case_search.case_search_adapter.index_name)
            self.assertEqual(
                update_1.properties,
                case_search.case_search_adapter.mapping["properties"],
            )
            self.assertEqual(update_2.name, cases.case_adapter.index_name)
            self.assertEqual(sorted(update_2.properties), ["closed", "domain"])

        with patch.object(Command, "write_migration_files", test_changes):
            call_command(
                "make_elastic_migration",
                "-c", "groups",
                "-c", "sms:sms-custom",
                "-d", "trashme_1",
                "-d", "trashme_2",
                "-u", "cases:closed,domain",
                "-u", "case_search",
            )

    def test_handle_empty_does_not_create_operations(self):

        def test_changes(self_, changes):
            migration, = changes.pop(Command.DJANGO_APP_LABEL)
            self.assertEqual([], migration.operations)

        with patch.object(Command, "write_migration_files", test_changes):
            call_command("make_elastic_migration", "-d", "trashme", "--empty")

    def test_handle_fails_for_invalid_migration_name(self):
        literal = "The migration name must be a valid Python identifier."
        with self.assertRaisesRegex(CommandError, f"^{re.escape(literal)}$"):
            call_command("make_elastic_migration", "-d", "trashme", "-n", "in-valid")

    def test_build_migration(self):
        creates = [(groups.group_adapter, "groups-custom")]
        updates = [(groups.group_adapter, {"domain": {"type": "text"}})]
        deletes = ["trashme"]
        command = Command()
        command.empty = False
        command.target_versions = []
        migration = command.build_migration(creates, updates, deletes)
        create_op, delete_op, update_op = sorted(migration.operations, key=sort_ops)
        self.assertIsInstance(create_op, CreateIndex)
        self.assertEqual(create_op.name, "groups-custom")
        self.assertIsInstance(delete_op, DeleteIndex)
        self.assertEqual(delete_op.name, "trashme")
        self.assertIsInstance(update_op, UpdateIndexMapping)
        self.assertEqual(update_op.name, groups.group_adapter.index_name)
        self.assertEqual(update_op.properties, {"domain": {"type": "text"}})

    def test_build_migration_fails_for_multiple_operations_on_the_same_index(self):
        conflict_index = groups.group_adapter.index_name
        updates = [(groups.group_adapter, {"domain": {"type": "text"}})]
        deletes = [conflict_index]
        command = Command()
        command.empty = False
        command.target_versions = []
        prefix = f"Multiple operations for the same index ({conflict_index}):"
        with self.assertRaisesRegex(CommandError, f"^{re.escape(prefix)}"):
            command.build_migration([], updates, deletes)

    def test_arrange_migration_changes_generates_correct_migration_name(self):

        def wrap(self_, original_migration):
            self.assertEqual("custom", original_migration.name)
            changes = og_method(self_, original_migration)
            arranged_migration, = changes.pop(self_.DJANGO_APP_LABEL)
            self.assertIs(original_migration, arranged_migration)
            number, delim, name = arranged_migration.name.partition("_")
            self.assertEqual("_", delim)
            self.assertGreaterEqual(int(number), 1)
            self.assertEqual(what4, name)
            wrap_calls.append(1)
            return {}  # so 'make_elastic_migration()' doesn't raise

        wrap_calls = []
        what4 = "cleanup_trash_index"
        og_method = Command.arrange_migration_changes
        with patch.object(Command, "arrange_migration_changes", wrap):
            # The --dry-run flag does not affect this test besides preventing
            # the 'write_migration_files()' method from writing files.
            call_command("make_elastic_migration", "-d", "trashme", "-n", what4, "--dry-run")
        self.assertEqual(1, sum(wrap_calls))

    def test_adapter_type(self):
        adapter = Command().adapter_type("groups")
        self.assertIs(adapter, groups.group_adapter)

    def test_adapter_type_raises_argumenttypeerror_for_invalid_cname(self):
        invalid = "bogus cname"
        prefix = f"Invalid index canonical name ({invalid}), choices: "
        with self.assertRaisesRegex(ArgumentTypeError, f"^{re.escape(prefix)}"):
            Command().adapter_type(invalid)

    @patch("corehq.apps.es.management.commands.make_elastic_migration.datetime", mock_datetime)
    def test_adapter_and_name_type(self):
        adapter, new_name = Command().adapter_and_name_type("groups")
        self.assertIs(adapter, groups.group_adapter)
        self.assertEqual("groups-20221228", new_name)

    def test_adapter_and_name_type_with_new_name(self):
        adapter, new_name = Command().adapter_and_name_type("groups:groups-custom")
        self.assertIs(adapter, groups.group_adapter)
        self.assertEqual("groups-custom", new_name)

    def test_adapter_and_name_type_raises_argumenttypeerror_for_empty_new_name(self):
        invalid = "groups:"
        literal = f"Invalid (empty) new name for create action: {invalid!r}"
        with self.assertRaisesRegex(ArgumentTypeError, f"^{re.escape(literal)}$"):
            Command().adapter_and_name_type(invalid)

    def test_adapter_and_properties_type(self):
        adapter, properties = Command().adapter_and_properties_type("groups:domain,name")
        self.assertIs(adapter, groups.group_adapter)
        self.assertEqual(["domain", "name"], sorted(properties))

    def test_adapter_and_properties_type_returns_all_properties_if_none_specified(self):
        adapter, properties = Command().adapter_and_properties_type("groups")
        self.assertIs(adapter, groups.group_adapter)
        self.assertEqual(groups.group_adapter.mapping["properties"], properties)

    def test_adapter_and_properties_type_raises_argumenttypeerror_for_invalid_property_name(self):
        invalid = "bogus property"
        prefix = f"Invalid property name for index: groups (got {invalid!r}, expected one of "
        with self.assertRaisesRegex(ArgumentTypeError, f"^{re.escape(prefix)}"):
            Command().adapter_and_properties_type(f"groups:{invalid}")

    def test_adapter_and_properties_type_raises_argumenttypeerror_for_empty_property_list(self):
        invalid = "groups:"
        literal = f"Invalid (empty) property list for update action: {invalid!r}"
        with self.assertRaisesRegex(ArgumentTypeError, f"^{re.escape(literal)}$"):
            Command().adapter_and_properties_type(invalid)


def sort_ops(operation):
    """Sort key for ensuring a migration operations list is in a specific order.
    """
    op_order = [CreateIndex, DeleteIndex, UpdateIndexMapping]
    return op_order.index(operation.__class__), operation.name
