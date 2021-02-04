from django.core.management.base import BaseCommand
from cloudant.client import Cloudant

COUCH2_HOST = "localhost"
COUCH2_PORT = 5984

COUCH3_HOST = "localhost"
COUCH3_PORT = 5985


def sync_dbs(source_db_obj, destination_db_obj):
    for doc in source_db_obj:
        doc_obj = destination_db_obj.create_document(doc)
        if not doc_obj.exists():
            print(f'Unable to sync ${doc_obj._id} in ${destination_db_obj.database_name}')


class Command(BaseCommand):
    help = """Script to copy local couchdb2 docs to couchdb3.
    It will iterate through all dbs sequentially and populate in couchdb3"""

    def handle(self, **options):
        couch2_client = Cloudant('', '', admin_party=True, url=f'http://{COUCH2_HOST}:{COUCH2_PORT}', connect=True)
        couch3_client = Cloudant('', '', admin_party=True, url=f'http://{COUCH3_HOST}:{COUCH3_PORT}', connect=True)

        source = couch2_client
        destination = couch3_client

        old_dbs = source.all_dbs()
        db_not_created = []

        for db_name in old_dbs:
            print(f'Copying db {db_name}')
            new_db_obj = destination.create_database(db_name)
            old_db_obj = source[db_name]
            if not new_db_obj.exists():
                db_not_created.append(db_name)
            else:
                sync_dbs(old_db_obj, new_db_obj)
        print("Clearing out connection objects")
        source.disconnect()
        destination.disconnect()
        print("Databases sucessfully copied")
