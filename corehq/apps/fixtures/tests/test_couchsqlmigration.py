from contextlib import contextmanager
from unittest.mock import patch
from pathlib import Path

from django.core.management import call_command
from django.db import connection, transaction
from django.test import SimpleTestCase, TestCase
from django.utils.functional import cached_property

from testil import tempdir

from ..management.commands.populate_lookuptables import Command as LookupTableCommand
from ..models import (
    FixtureDataType,
    LookupTable,
    TypeField,
)
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types


class TestLookupTableCouchToSQLDiff(SimpleTestCase):

    def test_no_diff(self):
        doc, obj = create_lookup_table()
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_domain(self):
        doc, obj = create_lookup_table()
        doc['domain'] = 'other-domain'
        self.assertEqual(
            self.diff(doc, obj),
            ["domain: couch value 'other-domain' != sql value 'some-domain'"],
        )

    def test_diff_is_global(self):
        doc, obj = create_lookup_table()
        obj.is_global = False
        self.assertEqual(
            self.diff(doc, obj),
            ["is_global: couch value True != sql value False"],
        )

    def test_diff_null_is_global(self):
        doc, obj = create_lookup_table(is_global=None)
        obj.is_global = False
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_missing_is_global(self):
        doc, obj = create_lookup_table()
        obj.is_global = False
        del doc["is_global"]
        self.assertEqual(self.diff(doc, obj), [])

    def test_diff_tag(self):
        doc, obj = create_lookup_table()
        obj.tag = 'cost'
        self.assertEqual(
            self.diff(doc, obj),
            ["tag: couch value 'price' != sql value 'cost'"],
        )

    def test_diff_fields(self):
        doc, obj = create_lookup_table()
        doc['fields'] = [{
            'doc_type': 'FixtureTypeField',
            'field_name': 'amount',
            'properties': [],
            'is_indexed': False,
        }]
        error, = self.diff(doc, obj)
        self.assertRegex(
            error,
            r"^fields: couch value \[[^q]+\] != sql value \[.+\]$",
        )

    def test_diff_old_style_fields(self):
        doc, obj = create_lookup_table()
        doc['fields'] = ['amount']
        error, = self.diff(doc, obj)
        self.assertRegex(
            error,
            r"^fields: couch value \[[^q]+\] != sql value \[.+\]$",
        )

    def test_diff_item_attributes(self):
        doc, obj = create_lookup_table()
        obj.item_attributes = ['age']
        self.assertEqual(
            self.diff(doc, obj),
            ["item_attributes: couch value ['name'] != sql value ['age']"],
        )

    def test_diff_doc_without_item_attributes(self):
        doc, obj = create_lookup_table()

        del doc["item_attributes"]
        self.assertEqual(
            self.diff(doc, obj),
            ["item_attributes: couch value None != sql value ['name']"],
        )

        obj.item_attributes = []
        self.assertEqual(self.diff(doc, obj), [])  # None in Couch == [] in SQL

    def test_diff_description(self):
        doc, obj = create_lookup_table()
        obj.description = 'about that'
        self.assertEqual(
            self.diff(doc, obj),
            ["description: couch value None != sql value 'about that'"],
        )

    def test_diff_multiple(self):
        doc, obj = create_lookup_table()
        obj.is_global = False
        doc["tag"] = 'cost'
        self.assertEqual(
            self.diff(doc, obj),
            [
                "tag: couch value 'cost' != sql value 'price'",
                "is_global: couch value True != sql value False",
            ],
        )

    def diff(self, doc, obj):
        return do_diff(LookupTableCommand, doc, obj)


class TestLookupTableCouchToSQLMigration(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = FixtureDataType.get_db()

    def tearDown(self):
        docs = list(get_all_docs_with_doc_types(self.db, ['FixtureDataType']))
        self.db.bulk_delete(docs)
        super().tearDown()

    def test_sync_to_couch(self):
        doc, obj = create_lookup_table()
        obj.save()
        couch_obj = self.db.get(obj._migration_couch_id)
        self.assertIsNone(couch_obj['description'], None)
        self.assertEqual(self.diff(couch_obj, obj), [])

        obj.tag = 'cost'
        obj.fields[0].name = 'value'
        obj.item_attributes = ['name', 'age']
        obj.description = 'about that'
        obj.save()
        doc = self.db.get(obj._migration_couch_id)
        self.assertEqual(doc['tag'], 'cost')
        self.assertEqual(doc['description'], 'about that')
        self.assertEqual(doc['item_attributes'], ['name', 'age'])
        self.assertEqual(doc['fields'][0], {
            'doc_type': 'FixtureTypeField',
            'field_name': 'value',
            'properties': [],
            'is_indexed': False,
        })

    def test_sync_to_sql(self):
        doc, obj = create_lookup_table(unwrap_doc=False)
        doc.save()
        self.assertEqual(
            self.diff(doc.to_json(), LookupTable.objects.get(id=doc._id)),
            [],
        )

        doc.tag = 'cost'
        doc.fields[0].field_name = 'value'
        doc.item_attributes = ['name', 'age']
        doc.save()
        obj = LookupTable.objects.get(id=doc._id)
        self.assertEqual(obj.tag, 'cost')
        self.assertEqual(obj.item_attributes, ['name', 'age'])
        self.assertEqual(obj.fields[0], TypeField(
            name='value',
            properties=[],
            is_indexed=False,
        ))

    def test_migration(self):
        doc, obj = create_lookup_table(unwrap_doc=False)
        doc.save(sync_to_sql=False)
        call_command('populate_lookuptables')
        self.assertEqual(
            self.diff(doc.to_json(), LookupTable.objects.get(id=doc._id)),
            [],
        )

    def test_migration_fixup_diffs(self):
        doc, obj = create_lookup_table(unwrap_doc=False)
        doc.save()
        doc.tag = 'cost'
        doc.fields[0].field_name = 'value'
        doc.item_attributes = ['name', 'age']
        doc.save(sync_to_sql=False)

        with templog() as log:
            call_command('populate_lookuptables', log_path=log.path)
            self.assertIn(f'Doc "{doc._id}" has differences:\n', log.content)
            self.assertIn("tag: couch value 'cost' != sql value 'price'", log.content)
            self.assertIn("fields: couch value [", log.content)
            self.assertIn("item_attributes: couch value [", log.content)

            call_command('populate_lookuptables', fixup_diffs=log.path)
            self.assertEqual(
                self.diff(doc.to_json(), LookupTable.objects.get(id=doc._id)),
                [],
            )

    def test_migration_with_old_doc_format(self):
        doc, obj = create_lookup_table()
        doc['fields'] = ['amount', 'qty']
        del doc['item_attributes']
        self.db.save_doc(doc)
        call_command('populate_lookuptables')
        self.assertEqual(
            self.diff(doc, LookupTable.objects.get(id=doc['_id'])),
            [],
        )

        doc['tag'] = 'cost'
        doc['fields'] = ['value', 'qty']
        assert 'item_attributes' not in doc, doc
        self.db.save_doc(doc)
        with templog() as log:
            call_command('populate_lookuptables', log_path=log.path)
            call_command('populate_lookuptables', fixup_diffs=log.path)
        self.assertEqual(
            self.diff(doc, LookupTable.objects.get(id=doc['_id'])),
            [],
        )

    def test_migration_race(self):
        def migration_runner():
            # use the same connection as main test thread
            connections[DEFAULT_DB_ALIAS] = test_connection
            call_command('populate_lookuptables')

        def migration_blocker(self, doc):
            concurrent_save.set()
            if not allow_migration.wait(timeout=10):
                raise RuntimeError("allow_migration timeout")
            return set()

        def diff(doc):
            return self.diff(doc.to_json(), LookupTable.objects.get(id=doc._id))

        from threading import Thread, Event
        from django.db import DEFAULT_DB_ALIAS, connections
        test_connection = connections[DEFAULT_DB_ALIAS]
        test_connection.inc_thread_sharing()
        try:
            concurrent_save = Event()
            allow_migration = Event()

            # save documents to Couch only (not SQL)
            price, obj = create_lookup_table(unwrap_doc=False)
            color, obj = create_lookup_table(unwrap_doc=False, tag="color")
            shape, obj = create_lookup_table(unwrap_doc=False, tag="shape")
            price.save(sync_to_sql=False)
            color.save(sync_to_sql=False)
            shape.save(sync_to_sql=False)

            with patch.object(LookupTableCommand, "get_ids_to_ignore", migration_blocker):
                migration = Thread(target=migration_runner)
                migration.start()  # loads Couch docs, blocks on get_ids_to_ignore

                if not concurrent_save.wait(timeout=10):
                    raise RuntimeError("concurrent_save timeout")
                # Save some SQL records before migration has a chance.
                # Should not cause migration to fail with IntegrityError.
                price.save()
                color.save()

                allow_migration.set()
                migration.join()

                self.assertEqual(diff(price), [])
                self.assertEqual(diff(color), [])
                self.assertEqual(diff(shape), [])
        finally:
            test_connection.dec_thread_sharing()

    def test_migration_race_to_orphaned_sql_doc(self):
        # Race condition:
        # - Couch & SQL objects both exist, in sync
        # - migration reads Couch object
        # - Couch object deleted by another process -> SQL object also deleted
        # - migration reads SQL to get list of objects to be created.
        #   SQL object is missing because it has been deleted.
        # - migration (re)creates SQL object with old/wrong Couch doc id
        # - other process attempts to create new lookup table with same
        #   (domain, tag), creates object in Couch, fails on save to SQL

        # setup: couch doc has different ID from sql doc with same domain, tag pair
        doc, obj = create_lookup_table(unwrap_doc=False)
        doc.save(sync_to_sql=False)
        assert obj._migration_couch_id != doc._id
        obj.save(sync_to_couch=False)

        with templog() as log, templog() as log2:
            call_command('populate_lookuptables', log_path=log.path)
            call_command('populate_lookuptables', fixup_diffs=log.path, log_path=log2.path)
            self.assertIn(f"Removed orphaned LookupTable row: {obj.id}", log2.content)
            self.assertIn(f"Recreated model for FixtureDataType with id {doc._id}", log2.content)

    def test_migration_deletes_duplicate_couch_docs(self):
        # Not sure how this scenario occurs, but --fixup-diffs should fix it

        # setup: multiple couch docs with same (domain, tag) pair
        dup_ids = set()
        for i in range(3):
            doc, obj = create_lookup_table(unwrap_doc=False)
            doc.save(sync_to_sql=False)
            dup_ids.add(doc._id)
        assert len(dup_ids) == 3, dup_ids

        with templog() as log, templog() as log2:
            call_command('populate_lookuptables', log_path=log.path)
            diffs = 0
            for dup_id in dup_ids:
                if f'Doc "{dup_id}" has differences:\n' in log.content:
                    diffs += 1
            self.assertEqual(diffs, 2, log.content)

            call_command('populate_lookuptables', fixup_diffs=log.path, log_path=log2.path)
            self.assertIn(f"Removed duplicate FixtureDataTypes: {sorted(dup_ids)[1:]}", log2.content)
            for dup_id in dup_ids:
                self.assertNotIn(f'Doc "{dup_id}" has differences:', log2.content)

    def test_migration_deletes_orphaned_tables_in_sql(self):
        # SQL rows became orphaned when bulk_delete() raised BulkSaveError (unhandled)
        docs = []
        for i in range(9):
            doc, obj = create_lookup_table(tag=f"price{i}", unwrap_doc=False)
            doc.save()
            docs.append(doc)
        docs.sort(key=lambda d: d._id)
        deleted = [docs[0], docs[-1]]
        deleted_ids = [d._id for d in deleted]
        FixtureDataType.bulk_delete(deleted)
        _, not_deleted = create_lookup_table(tag="price", unwrap_doc=False)
        not_deleted.save(sync_to_couch=False)

        with templog() as log, templog() as log2:
            call_command('populate_lookuptables', chunk_size=3, log_path=log.path)
            missing = 0
            for doc_id in deleted_ids + [not_deleted.id.hex]:
                if f'SQL row "{doc_id}" is missing in Couch\n' in log.content:
                    missing += 1
            self.assertEqual(missing, 3, log.content)
            self.assertEqual(log.content.count("missing in Couch"), 3, log.content)

            call_command('populate_lookuptables', fixup_diffs=log.path, log_path=log2.path)
            self.assertIn(f"Removed orphaned SQL rows: {deleted_ids}", log2.content)
            res = {'key': not_deleted.id.hex, 'error': 'not_found'}
            self.assertIn(f"not deleted in Couch: {res}", log2.content)
        self.assertFalse(LookupTable.objects.filter(id__in=deleted_ids).exists())

    def diff(self, doc, obj):
        return do_diff(LookupTableCommand, doc, obj)


def create_lookup_table(unwrap_doc=True, **extra):
    def fields_data(name="name"):
        return [
            {
                name: 'amount',
                'properties': [],
                'is_indexed': False,
            }, {
                name: 'qty',
                'properties': [],
                'is_indexed': False,
            },
        ]

    def data(**extra):
        return {
            'domain': 'some-domain',
            'is_global': True,
            'tag': 'price',
            'fields': fields_data(),
            'item_attributes': ['name'],
            **extra,
        }
    obj = jsonattrify(LookupTable, data(**extra))
    doc = FixtureDataType.wrap(data(
        doc_type="FixtureDataType",
        fields=fields_data("field_name"),
        **extra
    ))
    if unwrap_doc:
        doc = doc.to_json()
    return doc, obj


def do_diff(Command, doc, obj):
    result = Command.diff_couch_and_sql(doc, obj)
    return [x for x in result if x is not None]


def jsonattrify(model_type, data):
    obj = model_type()
    for name, value in data.items():
        field = model_type._meta.get_field(name)
        if hasattr(field, "builder"):
            value = field.builder.attrify(value)
        setattr(obj, name, value)
    return obj


@contextmanager
def atomic_check(using=None, savepoint='ignored'):
    with _atomic(using=using):
        yield
        connection.check_constraints()


_atomic = transaction.atomic


@contextmanager
def templog():
    with tempdir() as tmp:
        yield Log(tmp)


class Log:
    def __init__(self, tmp):
        self.path = Path(tmp) / "log.txt"

    @cached_property
    def content(self):
        with self.path.open() as lines:
            return "".join(lines)
