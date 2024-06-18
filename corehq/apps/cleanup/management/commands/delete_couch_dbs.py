from django.conf import settings
from django.core.management.base import BaseCommand

from couchdbkit.client import Database
from requests import HTTPError

from corehq.apps.cleanup.utils import abort, color_style, confirm, confirm_destructive_operation
from corehq.util.couchdb_management import couch_config


class Command(BaseCommand):
    help = "Delete couch databases. Used to reset an environment or delete a single database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )
        parser.add_argument(
            '--dbname',
            dest='dbname',
            help='A single couch database to be deleted.',
        )

    def handle(self, *, dbname=None, **options):
        if dbname is None:
            confirm_destructive_operation()
        else:
            style = color_style()
            print(style.ERROR("\nHEY! This is wicked dangerous, pay attention.\n"))
            confirm("Are you SURE you want to proceed?")

        print("This operation will delete the following DBs")

        if dbname is not None:
            database = Database(f"{settings.COUCH_DATABASE}__{dbname}")
            dbs = [(database.dbname, database)]
        else:
            dbs = couch_config.all_dbs_by_db_name.items()

        found_dbs_by_db_name = {}
        for name, db in dbs:
            try:
                print(" ", name.ljust(40), db.info()['doc_count'], "docs")
            except HTTPError as err:
                if 'Database does not exist' in str(err):
                    print(" ", name.ljust(40), "NOT FOUND, IGNORED")
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
        else:
            print("deletion done")
