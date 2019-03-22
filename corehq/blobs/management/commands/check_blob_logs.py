from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import json
import logging

import couchforms.models as xform
from couchdbkit.exceptions import ResourceNotFound
from django.core.management import BaseCommand, CommandError
from gevent.pool import Pool

import corehq.apps.accounting.models as acct
import corehq.apps.app_manager.models as apps
import corehq.apps.hqmedia.models as hqmedia
from corehq.apps.export import models as exports
from corehq.blobs import get_blob_db, CODES
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.mixin import BlobMetaRef
from corehq.blobs.util import set_max_connections
from corehq.util.decorators import change_log_level
from io import open


USAGE = "Usage: ./manage.py check_blob_logs [options] FILE [FILE [FILE]]"

BLOB_MIXIN_MODELS = {
    CODES.application: apps.Application,
    CODES.data_export: exports.CaseExportInstance,
    CODES.form_xml: xform.XFormInstance,
    CODES.form_attachment: xform.XFormInstance,
    CODES.multimedia: hqmedia.CommCareMultimedia,
    CODES.invoice: acct.InvoicePdf,
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
                 "should be a JSON record with blobmeta_id, domain, "
                 "type_code, parent_id, blob_key, and error fields",
        )
        parser.add_argument(
            '--migrate',
            action="store_true",
            default=False,
            help="Copy blobs found in old db to new db.",
        )
        parser.add_argument(
            '--num-workers',
            type=int,
            default=10,
            help="Worker pool size for concurrent processing.",
        )

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, files, migrate=False, num_workers=10, **options):
        set_max_connections(num_workers)
        blob_db = get_blob_db()
        if not isinstance(blob_db, MigratingBlobDB):
            raise CommandError(
                "Expected to find migrating blob db backend (got %r)" % blob_db)
        old_db = blob_db.old_db
        new_db = blob_db.new_db
        ignored = 0

        try:
            pool = Pool(size=num_workers)
            for filepath in files:
                print("Processing {}".format(filepath))
                with open(filepath, encoding='utf-8') as fh:
                    for line in fh:
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except ValueError:
                            ignored += 1
                            print(("Ignore {}", line))
                            continue
                        pool.spawn(process, rec, old_db, new_db, migrate)

            print("CTRL+C to abort")
            while not pool.join(timeout=10):
                print("waiting for {} workers to finish...".format(len(pool)))
        except KeyboardInterrupt:
            pass

        if ignored:
            print("Ignored {} malformed records".format(ignored))
        for type_code, stats in sorted(Stats.items.items()):
            try:
                group = BLOB_MIXIN_MODELS[type_code].__name__
            except KeyError:
                group = CODES.name_of(type_code, "type_code %s" % type_code)
            total = stats.new + stats.old + stats.noref + stats.lost
            print("{}: checked {} records".format(group, total))
            print("  Found in new db: {}".format(stats.new))
            print("  Found in old db: {}".format(stats.old))
            print("  Not referenced: {}".format(stats.noref))
            print("  Not found: {}".format(stats.lost))


def process(rec, old_db, new_db, migrate):
    category = check_blob(rec, old_db, new_db, migrate)
    stats = Stats.get(rec["type_code"])
    setattr(stats, category, getattr(stats, category) + 1)


def check_blob(rec, old_db, new_db, migrate=False):
    key = rec["blob_key"]

    if new_db.exists(key=key):
        return "new"

    if old_db.exists(key=key):
        if migrate:
            with old_db.get(key=key) as content:
                new_db.copy_blob(content, key=key)
            action = "Migrated from"
        else:
            action = "Found in"
        print("{} old db: {}".format(action, key))
        return "old"

    doc_type = BLOB_MIXIN_MODELS.get(rec["type_code"])
    if doc_type is not None:
        couchdb = doc_type.get_db()
        doc_id = rec["parent_id"]
        try:
            doc = couchdb.get(doc_id)
        except ResourceNotFound:
            print("Not referenced: {} doc not found".format(json.dumps(rec)))
            return "noref"

        for name, info in doc.get("external_blobs", {}).items():
            data = BlobMetaRef._normalize_json(couchdb.dbname, doc_id, info)
            if data["key"] == key:
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
    def get(cls, type_code):
        item = cls.items.get(type_code)
        if item is None:
            item = cls.items[type_code] = cls()
        return item

    def __init__(self):
        self.new = 0
        self.old = 0
        self.lost = 0
        self.noref = 0
