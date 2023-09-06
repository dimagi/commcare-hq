from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.cleanup.deletable_doc_types import DELETABLE_COUCH_DOC_TYPES
from dimagi.utils.couch.database import get_db


class Command(BaseCommand):
    help = "Delete deletable doc types in live database"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help="Print summary output without actually deleting",
        )

    def handle(self, dry_run, **options):
        by_db = defaultdict(list)
        for doc_type, db_names in DELETABLE_COUCH_DOC_TYPES.items():
            for db_name in db_names:
                by_db[db_name].append(doc_type)

        for db_name, doc_types in sorted(by_db.items(), key=lambda x: (x[0] or '')):
            if db_name and db_name not in settings.EXTRA_COUCHDB_DATABASES:
                print(f"There is no couch database '{db_name}'")
            else:
                deleteable_doc_types = self.handle_doc_type(doc_types, db_name)
                if not dry_run:
                    raise NotImplementedError(f"Would delete {deleteable_doc_types} but not yet implemented")

    def handle_doc_type(self, doc_types, db_name):
        db = get_db(db_name)
        if '*' in doc_types:
            print("Skipping doc_type '*'; whole database deletion not supported")
            doc_types = [doc_type for doc_type in doc_types if doc_type != '*']
        print(f"Finding deletable docs in database {db.dbname}")
        results = db.view(
            "all_docs/by_doc_type",
            group_level=1,
        ).all()
        all_doc_counts = {row['key'][0]: row['value'] for row in results}
        deletable_doc_counts = {
            doc_type: count
            for doc_type, count in all_doc_counts.items()
            if doc_type and doc_type.split('-')[0] in doc_types
        }
        for doc_type, count in sorted(deletable_doc_counts.items()):
            print(f"  {doc_type}\t{count}")
        if not deletable_doc_counts:
            print("  no deletable docs found")
        return deletable_doc_counts.keys()
