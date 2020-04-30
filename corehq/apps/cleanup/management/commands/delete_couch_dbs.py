from django.core.management.base import BaseCommand

from requests import HTTPError

from corehq.apps.cleanup.utils import abort, confirm_destructive_operation
from corehq.util.couchdb_management import couch_config


class Command(BaseCommand):
    help = "Delete all couch databases. Used to reset an environment."

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )

    def handle(self, *args, **options):
        confirm_destructive_operation()

        print("This operation will delete the following DBs")

        found_dbs_by_db_name = {}
        for name, db in couch_config.all_dbs_by_db_name.items():
            try:
                print(" ", name.ljust(40), db.info()['doc_count'], "docs")
            except HTTPError as err:
                if 'Database does not exist' in str(err):
                    continue
                raise
            found_dbs_by_db_name[name] = db

        if input("Still want to proceed? Type 'delete' (Last chance to back out)") != 'delete':
            abort()

        for name, db in found_dbs_by_db_name.items():
            if options['commit']:
                db.server.delete_db(db.dbname)
            print(f"deleted {name}")

        if not options['commit']:
            print("You need to run it with --commit for the deletion to happen")

        print("deletion done")
