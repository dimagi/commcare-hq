import re
import sys
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.utils.functional import cached_property

from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin

from testil import tempdir

from corehq.dbaccessors.couchapps.all_docs import delete_all_docs_by_doc_type

from ..management.commands.populate_sql_model_from_couch_model import PopulateSQLCommand


class TestPopulateSQLCommand(TestCase):

    def test_resume_migration(self):
        with templog() as log:
            create_doc("1")
            create_doc("2", ignore=True)
            create_doc("3")
            with stop_at_diff("3"):
                call_command(log_path=log.path)
            self.assertIn("Ignored model for TestDoc with id 2", log.content)
            self.assertIn("Created model for TestDoc with id 3", log.content)
            del log.content
            resume = Command._resume_iter_couch_view()
            self.assertEqual(resume.state.kwargs["startkey"], ['TestDoc', '2'])
            self.assertEqual(resume.state.progress["doc_count"], 2)
            self.assertFalse(resume.state.progress.get("is_completed"))

            create_doc("4", ignore=True)
            create_doc("5")
            output = call_command(log_path=log.path.parent)
            self.assertIn(f"log output file: {log.path}\n", output)
            self.assertIn(" 5/5 100%", output)
            self.assertIn("Created model for TestDoc with id 3", log.content)
            self.assertIn("Ignored model for TestDoc with id 4", log.content)
            self.assertEqual(log.content.count("Created model for TestDoc with id 1"), 1)
            resume = Command._resume_iter_couch_view()
            self.assertEqual(resume.state.progress["doc_count"], 5)
            self.assertTrue(resume.state.progress.get("is_completed"))

            create_doc("6")
            output = call_command(log_path=log.path.parent)
            self.assertEqual(
                output.strip(),
                "Migration is complete. Previously migrated 5 documents.\n"
                "Use --override-is-migration-completed to inspect or reset.",
            )

    def test_verify_does_not_change_resume_state(self):
        # bulk_create patch causes diffs
        with templog() as log, patch.object(FakeModel.objects, "bulk_create"):
            create_doc("1")
            create_doc("2", ignore=True)
            create_doc("3")
            with stop_at_diff("3"):
                call_command(log_path=log.path)
            log1 = log.content
            del log.content

            create_doc("4")
            verify_log = Log(log.path.parent, "verify.log")
            output = call_command(verify_only=True, log_path=verify_log.path)
            self.assertIn("Found 3 differences", output)
            self.assertIn('Doc "1" has differences', verify_log.content)
            self.assertIn('Doc "4" has differences', verify_log.content)
            self.assertEqual(log.content, log1, "original log should not be modified")
            resume = Command._resume_iter_couch_view()
            self.assertEqual(resume.state.progress["log_path"], str(log.path))
            self.assertEqual(resume.state.progress["doc_count"], 2)
            self.assertFalse(resume.state.progress.get("is_completed"))

    def test_fixup_diffs_does_not_change_resume_state(self):
        with templog() as log:
            create_doc("1")
            create_doc("2", ignore=True)
            create_doc("3")
            # bulk_create patch causes diffs
            with stop_at_diff("3"), patch.object(FakeModel.objects, "bulk_create"):
                call_command(log_path=log.path)
            self.assertIn('Doc "1" has differences', log.content)
            self.assertIn('Doc "3" has differences', log.content)
            log1 = log.content
            del log.content

            db = Command.couch_db()
            db.save_doc(db.get("3") | {"ignore": True})
            fixup_log = Log(log.path.parent, "fixup.log")
            output = call_command(fixup_diffs=log.path, log_path=fixup_log.path)
            self.assertIn("Found 0 differences", output)
            self.assertIn("Ignored 1 Couch documents", output)
            self.assertIn('Created model for TestDoc with id 1', fixup_log.content)
            self.assertIn("Ignored model for TestDoc with id 3", fixup_log.content)
            self.assertEqual(log.content, log1, "original log should not be modified")
            resume = Command._resume_iter_couch_view()
            self.assertEqual(resume.state.progress["log_path"], str(log.path))
            self.assertFalse(resume.state.progress.get("is_completed"))

    def test_domains_migration_does_not_change_resume_state(self):
        with templog() as log:
            create_doc("1", domain="two")
            create_doc("2", ignore=True)
            create_doc("3", domain="two")
            with stop_at_diff("3"):
                call_command(log_path=log.path)
            log1 = log.content
            del log.content

            create_doc("4", domain="two", ignore=True)
            create_doc("5")
            create_doc("6", domain="two")
            domains_log = Log(log.path.parent, "domains.log")
            output = call_command(log_path=domains_log.path, domains=["two"])
            self.assertIn("Ignored 1 Couch documents", output)
            self.assertIn('Ignored model for TestDoc with id 4', domains_log.content)
            self.assertIn('Created model for TestDoc with id 6', domains_log.content)
            self.assertEqual(log.content, log1, "original log should not be modified")
            resume = Command._resume_iter_couch_view()
            self.assertEqual(resume.state.progress["log_path"], str(log.path))
            self.assertFalse(resume.state.progress.get("is_completed"))

    def tearDown(self):
        delete_all_docs_by_doc_type(Command.couch_db(), [TestDoc.__name__])
        Command.discard_resume_state()
        FakeModel._created = []


def call_command(*, log_path, **options):
    options.setdefault("domains", None)
    options.setdefault("chunk_size", 1)
    options.setdefault("fixup_diffs", None)
    options.setdefault("override_is_completed", None)
    options.setdefault("debug", None)
    output = StringIO()
    with patch.object(sys, "stdout", output):
        try:
            Command().handle(log_path=log_path, **options)
        except SystemExit as exc:
            output.write(f"SystemExit: {exc}\n")
    outstr = output.getvalue()
    print(outstr)
    if "Migration is complete." not in outstr:
        log = re.search("log output file: ([^\n]+)", outstr).group(1)
        print(log)
        with open(log) as fh:
            print(fh.read())
    return outstr


def stop_at_diff(doc_id):
    def diff_stop(self, doc, *args):
        real_diff(self, doc, *args)
        if doc["_id"] == doc_id:
            raise KeyboardInterrupt
    real_diff = Command._do_diff
    return patch.object(Command, "_do_diff", diff_stop)


class Command(PopulateSQLCommand):

    @classmethod
    def couch_doc_type(cls):
        return TestDoc.__name__

    @classmethod
    def sql_class(cls):
        return FakeModel

    def get_ids_to_ignore(self, docs):
        return {d['_id'] for d in docs if d.get("ignore")}

    def _sql_query_from_docs(self, docs):
        ids = {doc["_id"] for doc in docs}
        return MockQueryset(obj for obj in FakeModel._created if obj._id in ids)

    @classmethod
    def diff_couch_and_sql(cls, couch, sql):
        return [cls.diff_attr(name, couch, sql) for name in ["_id", "domain"]]


class TestDoc(SyncCouchToSQLMixin, Document):
    class Meta:
        app_label = "couch"

    def _migration_get_fields(self):
        return ["domain"]


class FakeModel(SyncSQLToCouchMixin):
    _created = []
    _migration_couch_id_name = "_id"

    @classmethod
    def _migration_get_couch_model_class(cls):
        return TestDoc

    class objects:
        def bulk_create(objs, ignore_conflicts=False):
            FakeModel._created.extend(objs)

        def count():
            return len(FakeModel._created)

        def filter(**params):
            (key, val), = params.items()
            assert key.endswith("__in"), (key, val)
            attr = key[:-4]
            objs = [f for f in FakeModel._created if getattr(f, attr) in val]
            return MockQueryset(objs)

    def __repr__(self):
        return f"{type(self).__name__}(_id={self._id})"


def create_doc(_id, **data):
    return Command.couch_db().save_doc({
        "_id": _id,
        "doc_type": Command.couch_doc_type(),
        "domain": "one",
    } | data)


class MockQueryset(list):
    def only(self, *a, **kw):
        return self

    def count(self):
        return len(self)


@contextmanager
def templog():
    with tempdir() as tmp:
        yield Log(tmp)


class Log:
    def __init__(self, tmp, name="log.txt"):
        self.path = Path(tmp) / name

    @cached_property
    def content(self):
        with self.path.open() as lines:
            return "".join(lines)
