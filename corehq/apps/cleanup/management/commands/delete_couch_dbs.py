from django.core.management.base import BaseCommand

from corehq.util.couchdb_management import couch_config

from corehq.apps.cleanup.utils import confirm_destructive_operation, abort


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

        for name, db in couch_config.all_dbs_by_db_name.items():
            print(" ", name.ljust(40), db.info()['doc_count'], "docs")

        if input("Still want to proceed? Type 'delete' (Last chance to back out)") != 'delete':
            abort()

        for name, db in couch_config.all_dbs_by_db_name.items():
            if options['commit']:
                db.server.delete_db(db.dbname)
            print(f"deleted {name}")

        if not options['commit']:
            print("You need to run it with --commit for the deletion to happen")

        print("deletion done")
