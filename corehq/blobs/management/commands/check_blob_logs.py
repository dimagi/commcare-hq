from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import json
import logging

import couchforms.models as xform
from couchdbkit.exceptions import ResourceNotFound
from couchexport.models import SavedBasicExport
from django.core.management import BaseCommand, CommandError

import corehq.apps.app_manager.models as apps
from corehq.apps.export import models as exports
from corehq.blobs import get_blob_db
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.util.decorators import change_log_level


USAGE = "Usage: ./manage.py check_blob_logs [options] FILE [FILE [FILE]]"
BLOB_MIXIN_MODELS = {
    "Application": apps.Application,
    "Application-Deleted": apps.Application,
    "CaseExportInstance": exports.CaseExportInstance,
    "FormExportInstance": exports.FormExportInstance,
    "SavedBasicExport": SavedBasicExport,
    "XFormInstance": xform.XFormInstance,
}


class Command(BaseCommand):
    """Verify missing blobs in blob db backend migration log files.

    Example: ./manage.py check_blob_logs [options] migration-log.txt
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument(
            'files',
            nargs="+",
            help="Log files with blobs to check. Each line of the log file "
                 "should be a JSON record with blob_identifier, blob_bucket, "
                 "doc_type, and error fields",
        )
        parser.add_argument(
            '--migrate',
            action="store_true",
            default=False,
            help="Copy blobs found in old db to new db.",
        )

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, files, migrate=False, **options):
        blob_db = get_blob_db()
        if not isinstance(blob_db, MigratingBlobDB):
            raise CommandError(
                "Expected to find migrating blob db backend (got %r)" % blob_db)
        old_db = blob_db.old_db
        new_db = blob_db.new_db
        for filepath in files:
            with open(filepath) as fh:
                for line in fh:
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        print(("Ignore {}", line))
                        continue
                    if rec.get("error") != "not found":
                        print("Ignore {}".format(json.dumps(rec)))
                        continue
                    category = check_blob(rec, old_db, new_db, migrate)
                    stats = Stats.get(rec["doc_type"])
                    setattr(stats, category, getattr(stats, category) + 1)

        for doc_type, stats in sorted(Stats.items.items()):
            total = stats.new + stats.old + stats.noref + stats.lost
            print("{}: checked {} records".format(doc_type, total))
            print("  Found in new db: {}".format(stats.new))
            print("  Found in old db: {}".format(stats.old))
            print("  Not referenced: {}".format(stats.noref))
            print("  Not found: {}".format(stats.lost))


def check_blob(rec, old_db, new_db, migrate=False):
    identifier = rec["blob_identifier"]
    bucket = rec["blob_bucket"]

    if new_db.exists(identifier, bucket):
        return "new"

    if old_db.exists(identifier, bucket):
        if migrate:
            with old_db.get(identifier, bucket) as content:
                new_db.copy_blob(content, Info(identifier), bucket)
            migrated = " migrated"
        else:
            migrated = ""
        print("Found in old db: {}{}".format(json.dumps(rec), migrated))
        return "old"

    doc_type = BLOB_MIXIN_MODELS.get(rec["doc_type"])
    if doc_type is not None:
        try:
            doc = doc_type.get_db().get(rec["doc_id"])
        except ResourceNotFound:
            print("Not referenced: {} doc not found".format(json.dumps(rec)))
            return "noref"

        for name, info in doc.get("external_blobs", {}).items():
            if info["id"] == identifier:
                print("Missing: {} blob info: {}: {}".format(
                    json.dumps(rec),
                    repr(name),
                    info,
                ))
                return "lost"

        print("Not referenced: {}".format(json.dumps(rec)))
        return "noref"

    print("Missing: {}".format(json.dumps(rec)))
    return "lost"


class Stats(object):

    items = {}

    @classmethod
    def get(cls, doc_type):
        item = cls.items.get(doc_type)
        if item is None:
            item = cls.items[doc_type] = cls()
        return item

    def __init__(self):
        self.new = 0
        self.old = 0
        self.lost = 0
        self.noref = 0


class Info(object):

    def __init__(self, identifier):
        self.identifier = identifier
