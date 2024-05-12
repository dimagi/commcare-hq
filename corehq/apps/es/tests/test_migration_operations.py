import re
from io import StringIO
from textwrap import dedent
from unittest.mock import patch

from django.db import connection
from django.db.migrations import Migration
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.state import ProjectState
from django.test import SimpleTestCase, TestCase
from nose.tools import nottest

from corehq.apps.es.client import manager
from corehq.apps.es.index.settings import render_index_tuning_settings
from corehq.apps.es.migration_operations import (
    CreateIndex,
    CreateIndexIfNotExists,
    DeleteIndex,
    MappingUpdateFailed,
    UpdateIndexMapping,
    make_mapping_meta,
)
from corehq.apps.es.tests.test_client import patch_elastic_version
from corehq.apps.es.tests.utils import es_test
from corehq.pillows.management.commands.print_elastic_mappings import transform_string_to_text_and_keyword
from corehq.util.es.elasticsearch import NotFoundError, RequestError


class BaseCase(TestCase):

    maxDiff = None

    index = "test_index_migrations"

    def tearDown(self):
        # trash the test index, which may or may not exist, depending on the test
        try:
            manager.index_delete(self.index)
        except NotFoundError:
            pass
        super().tearDown()

    def assertIndexExists(self, index):
        self.assertTrue(manager.index_exists(index))

    def assertIndexDoesNotExist(self, index):
        self.assertFalse(manager.index_exists(index))

    def assertIndexMappingMatches(self, index, type_, mapping):
        """Test that the mapping matches, with exception of the
        ``fetched_mapping["_meta"]["created"]`` value, which must exist but the
        actual value is not compared.
        """
        fetched_mapping = manager.index_get_mapping(index, type_)
        # pop and verify the created value exists
        self.assertTrue(bool(fetched_mapping["_meta"].pop("created", False)))
        self.assertEqual(mapping, fetched_mapping)

    def assertIndexHasAnalysis(self, index, analysis):
        self.assertEqual(
            {"analysis": analysis},
            manager.index_get_settings(index, values=["analysis"]),
        )

    def assertIndexHasTuningSettings(self, index, settings_key):
        expected = render_index_tuning_settings(settings_key)
        got = manager.index_get_settings(index, values=expected)
        for key, value in got.items():
            # Cast the values fetched from elasticsearch with the expected type
            # because Elasticsearch returns values as strings, but all existing
            # HQ code uses integers for the values of 'number_of_replicas' and
            # 'number_of_shards'.
            got[key] = type(expected[key])(value)
        self.assertEqual(expected, got)


@es_test
class TestCreateIndex(BaseCase):

    type = "test_doc"
    mapping = {
        "_meta": {},
        "properties": {
            "value": {"type": "text"},
        },
    }
    analysis = {"analyzer": {"default": {
        "filter": ["lowercase"],
        "type": "custom",
        "tokenizer": "whitespace",
    }}}
    settings_key = "test"
    create_index_args = (BaseCase.index, type, mapping, analysis, settings_key)

    def test_creates_index(self):
        migration = TestMigration(CreateIndex(*self.create_index_args))
        self.assertIndexDoesNotExist(self.index)
        migration.apply()
        self.assertIndexExists(self.index)
        self.assertIndexMappingMatches(self.index, self.type, self.mapping)
        self.assertIndexHasAnalysis(self.index, self.analysis)
        self.assertIndexHasTuningSettings(self.index, self.settings_key)

    def test_creates_index_with_comment(self):
        comment = "test comment"
        migration = TestMigration(
            CreateIndex(*self.create_index_args, comment=comment)
        )
        self.assertIndexDoesNotExist(self.index)
        migration.apply()
        self.assertIndexExists(self.index)
        expected = self.mapping.copy()
        expected["_meta"]["comment"] = comment
        self.assertIndexMappingMatches(self.index, self.type, expected)
        self.assertIndexHasAnalysis(self.index, self.analysis)
        self.assertIndexHasTuningSettings(self.index, self.settings_key)

    def test_index_creation_is_skipped_if_es_version_not_targetted(self):
        migration = TestMigration(
            CreateIndex(*self.create_index_args, es_versions=[5])
        )
        self.assertIndexDoesNotExist(self.index)
        with patch_elastic_version(manager, "2.4.6"):
            migration.apply()
        self.assertIndexDoesNotExist(self.index)

    def test_index_creation_if_es_version_is_targetted(self):
        migration = TestMigration(
            CreateIndex(*self.create_index_args, es_versions=[2, 5])
        )
        self.assertIndexDoesNotExist(self.index)
        with patch_elastic_version(manager, "2.4.6"):
            migration.apply()
        self.assertIndexExists(self.index)

    def test_fails_if_index_exists(self):
        manager.index_create(self.index)
        self.assertIndexExists(self.index)
        migration = TestMigration(CreateIndex(*self.create_index_args))
        with self.assertRaises(RequestError) as context:
            migration.apply()
        self.assertEqual(context.exception.error, "index_already_exists_exception")

    def test_reverse_deletes_index(self):
        migration = TestMigration(CreateIndex(*self.create_index_args))
        migration.apply()
        self.assertIndexExists(self.index)
        migration.unapply()
        self.assertIndexDoesNotExist(self.index)

    def test_reverse_fails_if_index_does_not_exist(self):
        migration = TestMigration(CreateIndex(*self.create_index_args))
        self.assertIndexDoesNotExist(self.index)
        with self.assertRaises(NotFoundError):
            migration.unapply()

    def test_render_index_metadata(self):
        type_ = object()
        mapping = {"prop": object()}
        analysis = object()
        settings_key = "test"
        comment = object()
        metadata = CreateIndex.render_index_metadata(type_, mapping, analysis, settings_key, comment)
        tuning_values = render_index_tuning_settings(settings_key)
        self.assertTrue(bool(metadata["mappings"][type_]["_meta"].pop("created")))
        self.assertEqual(
            {
                "mappings": {type_: dict(
                    _meta={"comment": comment},
                    **mapping,
                )},
                "settings": dict(
                    analysis=analysis,
                    **tuning_values,
                ),
            },
            metadata,
        )

    def test_render_index_metadata_returns_dict_copies_for_mapping(self):
        type_ = object()
        meta_ = {object(): object()}
        mapping = {"prop": object(), "_meta": meta_}
        metadata = CreateIndex.render_index_metadata(type_, mapping, None, None, None)
        rendered_mapping = metadata["mappings"][type_]
        rendered_meta = rendered_mapping["_meta"]
        self.assertTrue(bool(rendered_meta.pop("created")))
        assert_copies = [
            (mapping, rendered_mapping),
            (meta_, rendered_meta),
        ]
        rendered_mapping = metadata["mappings"][type_]
        for expected, rendered in assert_copies:
            self.assertEqual(expected, rendered)
            self.assertIsNot(expected, rendered)

    def test_render_index_metadata_adds_meta_created(self):
        mapping = {}
        type_ = object()
        created = "the time right now"
        with patch("corehq.apps.es.migration_operations.datetime", get_datetime_mock(created)):
            metadata = CreateIndex.render_index_metadata(type_, mapping, None, None, None)
        self.assertEqual(
            metadata["mappings"][type_]["_meta"]["created"],
            created,
        )

    def test_render_index_metadata_overrides_existing_created_date(self):
        type_ = object()
        created = "some time in the past"
        mapping = {"_meta": {"created": created}}
        metadata = CreateIndex.render_index_metadata(type_, mapping, None, None, None)
        self.assertNotEqual(
            metadata["mappings"][type_]["_meta"]["created"],
            created,
        )

    def test_render_index_metadata_uses_existing_comment_if_op_comment_is_none(self):
        type_ = object()
        comment = "this will persist"
        mapping = {"_meta": {"comment": comment}}
        metadata = CreateIndex.render_index_metadata(type_, mapping, None, None, None)
        self.assertEqual(
            metadata["mappings"][type_]["_meta"]["comment"],
            comment,
        )

    def test_render_index_metadata_does_not_add_missing_comment_if_op_comment_is_none(self):
        type_ = object()
        mapping = {"_meta": {}}
        metadata = CreateIndex.render_index_metadata(type_, mapping, None, None, None)
        self.assertNotIn("comment", metadata["mappings"][type_]["_meta"])

    def test_render_index_metadata_sets_comment_if_op_comment_is_not_none(self):
        type_ = object()
        mapping = {"_meta": {"comment": "this will be overwritten"}}
        comment = "this is the new comment"
        metadata = CreateIndex.render_index_metadata(type_, mapping, None, None, comment)
        self.assertEqual(
            metadata["mappings"][type_]["_meta"]["comment"],
            comment,
        )

    def test_render_index_metadata_returns_verbatim_analysis(self):
        analysis = object()
        metadata = CreateIndex.render_index_metadata(None, {}, analysis, None, None)
        self.assertIs(analysis, metadata["settings"]["analysis"])

    def test_render_index_metadata_uses_environment_tuning_settings(self):
        settings_key = object()
        with patch("corehq.apps.es.migration_operations.render_index_tuning_settings") as mock:
            CreateIndex.render_index_metadata(None, {}, None, settings_key, None)
        mock.assert_called_once_with(settings_key)

    def test_describe(self):
        operation = CreateIndex(*self.create_index_args)
        self.assertEqual(
            f"Create Elasticsearch index {self.index!r}",
            operation.describe(),
        )

    def test_deconstruct(self):
        args = ["test", "test", {}, {}, "test"]
        operation = CreateIndex(*args)
        self.assertEqual(
            operation.deconstruct(),
            (CreateIndex.__qualname__, args, {'es_versions': []}),
        )

    def test_deconstruct_omits_mapping__meta(self):
        name, type_, analysis, settings_key = ("test", "test", {}, "test")
        mapping = {
            "top_level": True,
            "_meta": {"key": "value"},
        }
        operation = CreateIndex(name, type_, mapping, analysis, settings_key)
        self.assertEqual(
            operation.deconstruct(),
            (
                CreateIndex.__qualname__,
                [
                    name,
                    type_,
                    {"top_level": True},
                    analysis,
                    settings_key,
                ],
                {'es_versions': []},
            ),
        )

    def test_deconstruct_with_comment(self):
        args = ["test", "test", {}, {}, "test", "this is the comment"]
        operation = CreateIndex(*args)
        self.assertEqual(
            operation.deconstruct(),
            (
                CreateIndex.__qualname__,
                args[:-1],
                {"comment": "this is the comment", "es_versions": []},
            ),
        )

    def test_deconstruct_with_es_versions(self):
        args = ["test", "test", {}, {}, "test", "this is the comment", [5, 6]]

        operation = CreateIndex(*args)
        self.assertEqual(
            operation.deconstruct(),
            (
                CreateIndex.__qualname__,
                args[:-2],
                {"comment": "this is the comment", "es_versions": [5, 6]},
            ),
        )


@es_test
class TestCreateIndexIfNotExists(BaseCase):

    type = "test_doc"
    mapping = {
        "_meta": {},
        "properties": {
            "value": {"type": "text"},
        },
    }
    analysis = {"analyzer": {"default": {
        "filter": ["lowercase"],
        "type": "custom",
        "tokenizer": "whitespace",
    }}}
    settings_key = "test"
    create_index_args = (BaseCase.index, type, mapping, analysis, settings_key)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CreateIndexIfNotExists = CreateIndexIfNotExists

    def test_does_not_fail_if_index_exists(self):
        manager.index_create(self.index)
        new_mapping = {
            "properties": {
                "some_other_val": {"type": "text"},
            },
        }
        manager.index_put_mapping(self.index, self.type, new_mapping)
        self.assertIndexExists(self.index)

        migration = TestMigration(self.CreateIndexIfNotExists(*self.create_index_args))
        migration.apply()

        # Index still exists after running migration
        self.assertIndexExists(self.index)

        fetched_mapping = manager.index_get_mapping(self.index, self.type)
        # existing mapping is not changed
        self.assertEqual(fetched_mapping, new_mapping)

    def test_creates_index_if_not_exists(self):
        self.assertIndexDoesNotExist(self.index)
        migration = TestMigration(self.CreateIndexIfNotExists(*self.create_index_args))
        migration.apply()
        # Index is created with new mappings
        self.assertIndexExists(self.index)
        self.assertIndexMappingMatches(self.index, self.type, self.mapping)

    def test_reverse_is_noop(self):
        migration = TestMigration(self.CreateIndexIfNotExists(*self.create_index_args))
        migration.apply()
        self.assertIndexExists(self.index)
        migration.unapply()
        self.assertIndexExists(self.index)


@es_test
class TestDeleteIndex(BaseCase):

    def test_deletes_index(self):
        migration = TestMigration(DeleteIndex(self.index))
        manager.index_create(self.index)
        self.assertIndexExists(self.index)
        migration.apply()
        self.assertIndexDoesNotExist(self.index)

    def test_deletes_index_skipped_if_targetted_es_version_not_match(self):
        migration = TestMigration(DeleteIndex(self.index, es_versions=[5]))
        manager.index_create(self.index)
        self.assertIndexExists(self.index)
        with patch_elastic_version(manager, "2.4.6"):
            migration.apply()
        self.assertIndexExists(self.index)

    def test_deletes_index_when_target_es_version_matches(self):
        migration = TestMigration(DeleteIndex(self.index, es_versions=[2, 5]))
        manager.index_create(self.index)
        self.assertIndexExists(self.index)
        with patch_elastic_version(manager, "2.4.6"):
            migration.apply()
        self.assertIndexDoesNotExist(self.index)

    def test_fails_if_index_does_not_exist(self):
        migration = TestMigration(DeleteIndex(self.index))
        self.assertIndexDoesNotExist(self.index)
        with self.assertRaises(NotFoundError):
            migration.apply()

    def test_is_irreversible_without_reverse_params(self):
        migration = TestMigration(DeleteIndex(self.index))
        with self.assertRaises(IrreversibleError):
            migration.unapply()

    def test_reverse_creates_index_using_reverse_params(self):
        type_ = "Test"
        analysis = {"analyzer": {"default": {
            "filter": ["lowercase"],
            "type": "custom",
            "tokenizer": "whitespace",
        }}}
        settings_key = "test"
        delete_op = DeleteIndex(
            self.index,
            reverse_params=(type_, {}, analysis, settings_key),
        )
        migration = TestMigration(delete_op)
        self.assertIndexDoesNotExist(self.index)
        migration.unapply()
        self.assertIndexExists(self.index)
        expected_mapping = {"_meta": {"comment": f"Reversal of {delete_op!r}"}}
        self.assertIndexMappingMatches(self.index, type_, expected_mapping)
        self.assertIndexHasAnalysis(self.index, analysis)
        self.assertIndexHasTuningSettings(self.index, settings_key)

    def test_reverse_fails_if_index_exists(self):
        manager.index_create(self.index)
        self.assertIndexExists(self.index)
        migration = TestMigration(
            DeleteIndex(self.index, reverse_params=("test", {}, {}, "test"))
        )
        with self.assertRaises(RequestError) as context:
            migration.unapply()
        self.assertEqual(context.exception.error, "index_already_exists_exception")

    def test_describe(self):
        operation = DeleteIndex(self.index)
        self.assertEqual(
            f"Delete Elasticsearch index {self.index!r}",
            operation.describe(),
        )

    def test_deconstruct(self):
        name = "name"
        operation = DeleteIndex(name)
        self.assertEqual(
            operation.deconstruct(),
            (DeleteIndex.__qualname__, [name], {'es_versions': []}),
        )

    def test_deconstruct_with_reverse_params(self):
        name = "name"
        reverse_params = ("type", {}, {}, "settings_key")
        operation = DeleteIndex(name, reverse_params)
        self.assertEqual(
            operation.deconstruct(),
            (
                DeleteIndex.__qualname__,
                [name],
                {"reverse_params": reverse_params, "es_versions": []},
            ),
        )


@es_test
class TestUpdateIndexMapping(BaseCase):

    def setUp(self):
        super().setUp()
        self.type = "test_doc"
        self.mapping = {
            "_all": {"enabled": False},
            "_meta": {"test_meta": "this is a test"},
            "date_detection": False,
            "dynamic": True,
            "dynamic_date_formats": ["yyyy-MM-dd"],
            "properties": {"prop": {"type": "text"}},
        }
        CreateIndex(self.index, self.type, self.mapping, {}, "test").run()

    def test_updates_meta(self):
        before_update = manager.index_get_mapping(self.index, self.type)["_meta"]
        new_created = "some date value"
        mock = get_datetime_mock(new_created)
        with patch("corehq.apps.es.migration_operations.datetime", mock):
            TestMigration(UpdateIndexMapping(self.index, self.type, {})).apply()
        after_update = manager.index_get_mapping(self.index, self.type)["_meta"]
        self.assertEqual(new_created, after_update["created"])
        self.assertNotEqual(
            after_update.pop("created"),
            before_update.pop("created"),
        )
        self.assertEqual(after_update, before_update)

    def test_updates_meta_comment_if_provided(self):
        mapping_meta = manager.index_get_mapping(self.index, self.type)["_meta"]
        comment = "test comment"  # any value that differs from the initial
        self.assertNotEqual(mapping_meta.get("comment"), comment)
        TestMigration(UpdateIndexMapping(self.index, self.type, {}, comment=comment)).apply()
        mapping_meta = manager.index_get_mapping(self.index, self.type)["_meta"]
        self.assertEqual(comment, mapping_meta["comment"])

    def test_adds_new_properties(self):
        properties = manager.index_get_mapping(self.index, self.type)["properties"]
        new_properties = {
            "new_str_prop": {"type": "text"},
            "new_int_prop": {"type": "integer"},
        }
        self.assertNotEqual(properties, new_properties)
        TestMigration(UpdateIndexMapping(self.index, self.type, new_properties)).apply()
        properties.update(new_properties)
        self.assertEqual(
            properties,
            manager.index_get_mapping(self.index, self.type)["properties"],
        )

    def test_adds_new_properties_if_targeted_es_version_matches(self):
        properties = manager.index_get_mapping(self.index, self.type)["properties"]
        new_properties = {
            "new_str_prop": {"type": "text"},
            "new_int_prop": {"type": "integer"},
        }
        self.assertNotEqual(properties, new_properties)
        with patch_elastic_version(manager, "2.4.6"):
            TestMigration(UpdateIndexMapping(self.index, self.type, new_properties, es_versions=[2])).apply()
        properties.update(new_properties)
        self.assertEqual(
            properties,
            manager.index_get_mapping(self.index, self.type)["properties"],
        )

    def test_new_properties_not_added_if_targeted_es_version_not_matches(self):
        properties = manager.index_get_mapping(self.index, self.type)["properties"]
        new_properties = {
            "new_str_prop": {"type": "text"},
            "new_int_prop": {"type": "integer"},
        }

        self.assertNotEqual(properties, new_properties)
        with patch_elastic_version(manager, "2.4.6"):
            TestMigration(UpdateIndexMapping(self.index, self.type, new_properties, es_versions=[5])).apply()

        self.assertEqual(
            properties,
            manager.index_get_mapping(self.index, self.type)["properties"],
        )

    def test_updates_only_meta_and_properties_items_and_retains_all_others(self):

        def exclude_meta_and_properties(mapping):
            del mapping["_meta"], mapping["properties"]
            return mapping

        before_update = manager.index_get_mapping(self.index, self.type)
        TestMigration(UpdateIndexMapping(self.index, self.type, {})).apply()
        after_update = manager.index_get_mapping(self.index, self.type)
        self.assertEqual(
            exclude_meta_and_properties(before_update),
            exclude_meta_and_properties(after_update),
        )

    def test_extends_existing_property_fields(self):
        properties = manager.index_get_mapping(self.index, self.type)["properties"]
        property_update = {"prop": {
            "type": "text",
            "fields": {"raw_value": {
                "type": "keyword",
            }},
        }}
        self.assertNotEqual(properties, property_update)
        TestMigration(UpdateIndexMapping(self.index, self.type, property_update)).apply()
        properties.update(property_update)
        self.assertEqual(
            properties,
            manager.index_get_mapping(self.index, self.type)["properties"],
        )

    def test_tolerates_existing_property_noop(self):
        properties = manager.index_get_mapping(self.index, self.type)["properties"]
        property_noop = self.mapping["properties"]
        self.assertEqual(properties, property_noop)
        TestMigration(UpdateIndexMapping(self.index, self.type, property_noop)).apply()
        self.assertEqual(
            properties,
            manager.index_get_mapping(self.index, self.type)["properties"],
        )

    def test_fails_for_existing_property_type_change(self):
        self.assertEqual(
            manager.index_get_mapping(self.index, self.type)["properties"]["prop"],
            {"type": "text"},
        )
        migration = TestMigration(UpdateIndexMapping(
            self.index,
            self.type,
            {"prop": {"type": "integer"}},
        ))
        literal = (
            "TransportError(400, 'illegal_argument_exception', 'mapper [prop] "
            "of different type, current_type [text], merged_type [integer]')"
        )
        with self.assertRaisesRegex(RequestError, f"^{re.escape(literal)}$"):
            migration.apply()

    def test_fails_for_changing_existing_property_index_values(self):
        self.assertEqual(
            manager.index_get_mapping(self.index, self.type)["properties"]["prop"],
            {"type": "text"},
        )
        migration = TestMigration(UpdateIndexMapping(
            self.index,
            self.type,
            {"prop": {"type": "keyword"}},
        ))
        literal = (
            "TransportError(400, 'illegal_argument_exception', "
            "'mapper [prop] of different type, current_type [text], merged_type [keyword]')"
        )
        with self.assertRaisesRegex(RequestError, f"^{re.escape(literal)}$"):
            migration.apply()

    def test_mapping_update_generates_diff(self):
        # update the current mapping._meta.created to get a deterministic diff
        manager.index_put_mapping(self.index, self.type, {"_meta": {"created": "initial"}})
        update_op = UpdateIndexMapping(
            self.index,
            self.type,
            {"number": {"type": "integer"}},
        )
        stream = StringIO()
        with (
            patch("corehq.apps.es.migration_operations.datetime", get_datetime_mock("updated")),
            patch.object(update_op, "stream", stream),
        ):
            TestMigration(update_op).apply()
        self.assertEqual(
            dedent("""\
                --- before.py
                +++ after.py
                @@ -3,7 +3,7 @@
                         "enabled": False
                     },
                     "_meta": {
                -        "created": "initial"
                +        "created": "updated"
                     },
                     "date_detection": False,
                     "dynamic": "true",
                @@ -11,6 +11,9 @@
                         "yyyy-MM-dd"
                     ],
                     "properties": {
                +        "number": {
                +            "type": "integer"
                +        },
                         "prop": {
                             "type": "text"
                         }
            """),
            stream.getvalue(),
        )

    def test_mapping_update_with_print_diff_false_does_not_generate_diff(self):
        update_op = UpdateIndexMapping(
            self.index,
            self.type,
            {"number": {"type": "integer"}},
            print_diff=False,
        )
        stream = StringIO()
        with patch.object(update_op, "stream", stream):
            TestMigration(update_op).apply()
        self.assertEqual("", stream.getvalue())

    def test_fails_if_index_does_not_exist(self):
        index = "missing"
        migration = TestMigration(UpdateIndexMapping(index, self.type, {}))
        self.assertIndexDoesNotExist(index)
        with self.assertRaises(NotFoundError):
            migration.apply()

    def test_raises_mappingupdatefailed_if_acknowledgement_is_missing(self):
        migration = TestMigration(UpdateIndexMapping(self.index, self.type, {}))
        with (
            patch.object(manager, "index_put_mapping", return_value={}),
            self.assertRaises(MappingUpdateFailed),
        ):
            migration.apply()

    def test_is_irreversible(self):
        migration = TestMigration(UpdateIndexMapping(self.index, self.type, {}))
        with self.assertRaises(IrreversibleError):
            migration.unapply()

    def test_describe(self):
        operation = UpdateIndexMapping(self.index, self.type, {})
        self.assertEqual(
            f"Update the mapping for Elasticsearch index {self.index!r}",
            operation.describe(),
        )

    def test_deconstruct(self):
        args = ["name", "type", {}]
        operation = UpdateIndexMapping(*args)
        self.assertEqual(
            operation.deconstruct(),
            (UpdateIndexMapping.__qualname__, args, {'es_versions': []}),
        )

    def test_deconstruct_with_comment(self):
        args = ["name", "type", {}, "this is the comment"]
        operation = UpdateIndexMapping(*args)
        self.assertEqual(
            operation.deconstruct(),
            (
                UpdateIndexMapping.__qualname__,
                args[:-1],
                {
                    "comment": "this is the comment",
                    "es_versions": [],
                }
            ),
        )

    def test_deconstruct_no_print_diff(self):
        args = ["name", "type", {}]
        operation = UpdateIndexMapping(*args, print_diff=False)
        self.assertEqual(
            operation.deconstruct(),
            (UpdateIndexMapping.__qualname__, args, {"print_diff": False, 'es_versions': []}),
        )


@es_test
class TestMakeMappingMeta(SimpleTestCase):

    def test_make_mapping_meta_adds_created_utcnow_as_isoformat(self):
        created = "mock created value"
        mock = get_datetime_mock(created)
        with patch("corehq.apps.es.migration_operations.datetime", mock):
            self.assertEqual(created, make_mapping_meta()["created"])
        self.assertEqual(1, mock.isoformat_called_count)
        self.assertEqual(1, mock.utcnow_called_count)

    def test_make_mapping_only_adds_created_and_comment(self):
        self.assertEqual(
            ["comment", "created"],
            sorted(make_mapping_meta("test comment")),
        )

    def test_make_mapping_meta_omits_comment_by_default(self):
        self.assertNotIn("comment", make_mapping_meta())

    def test_make_mapping_meta_adds_comment_if_provided(self):
        comment = object()
        self.assertEqual(comment, make_mapping_meta(comment)["comment"])


class TestMappingTransformFunctions(SimpleTestCase):

    def test_transform_string_to_text_and_keyword(self):
        old_mapping = {
            "_meta": {"created": "now"},
            "properties": {
                "value": {"type": "text"},
                "dict_val": {
                    "properties": {"nested_val": {"type": "keyword"}}
                }

            },
        }

        transformed_mappings = transform_string_to_text_and_keyword(old_mapping)

        expected_mappings = {
            "_meta": {"created": "now"},
            "properties": {
                "value": {"type": "text"},
                "dict_val": {
                    "properties": {"nested_val": {"type": "keyword"}}
                }

            },
        }
        self.assertEqual(transformed_mappings, expected_mappings)


def get_datetime_mock(created):
    """Returns a custom mock for ``datetime.datetime`` which implements the
    functionality used to generate Elastic ``mapping._meta.created`` values.

    :param created: a value that the mock should provide as the utcnow value.
    """
    class mock_datetime:

        isoformat_called_count = 0
        utcnow_called_count = 0

        @classmethod
        def isoformat(cls, value):
            cls.isoformat_called_count += 1
            return value

        @classmethod
        def utcnow(cls):
            cls.utcnow_called_count += 1
            return created

    return mock_datetime


@nottest
class TestMigration(Migration):

    def __init__(self, operation):
        super().__init__("test_migration", "test_label")
        self.operations = [operation]

    def apply(self):
        with connection.schema_editor() as schema_editor:
            super().apply(ProjectState(), schema_editor)

    def unapply(self):
        with connection.schema_editor() as schema_editor:
            super().unapply(ProjectState(), schema_editor)
