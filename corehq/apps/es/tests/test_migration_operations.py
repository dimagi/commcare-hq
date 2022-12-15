from unittest.mock import patch

from django.db import connection
from django.db.migrations import Migration
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.state import ProjectState
from django.test import TestCase
from nose.tools import nottest

from corehq.apps.es.client import manager
from corehq.apps.es.index.settings import render_index_tuning_settings
from corehq.apps.es.migration_operations import (
    CreateIndex,
    DeleteIndex,
)
from corehq.apps.es.tests.utils import es_test
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
            "value": {"type": "string"},
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

    def test_fails_if_index_exists(self):
        manager.index_create(self.index)
        self.assertIndexExists(self.index)
        migration = TestMigration(CreateIndex(*self.create_index_args))
        with self.assertRaises(RequestError) as mock:
            migration.apply()
        self.assertEqual(mock.exception.error, "index_already_exists_exception")

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

    def test_render_index_metadata_adds_created_utcnow_as_isoformat(self):

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

        mapping = {}
        type_ = object()
        created = "the time right now"
        with patch("corehq.apps.es.migration_operations.datetime", mock_datetime):
            metadata = CreateIndex.render_index_metadata(type_, mapping, None, None, None)
        self.assertEqual(
            metadata["mappings"][type_]["_meta"]["created"],
            created,
        )
        self.assertEqual(1, mock_datetime.isoformat_called_count)
        self.assertEqual(1, mock_datetime.utcnow_called_count)

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


@es_test
class TestDeleteIndex(BaseCase):

    def test_deletes_index(self):
        migration = TestMigration(DeleteIndex(self.index))
        manager.index_create(self.index)
        self.assertIndexExists(self.index)
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
        with self.assertRaises(RequestError) as mock:
            migration.unapply()
        self.assertEqual(mock.exception.error, "index_already_exists_exception")

    def test_describe(self):
        operation = DeleteIndex(self.index)
        self.assertEqual(
            f"Delete Elasticsearch index {self.index!r}",
            operation.describe(),
        )


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
