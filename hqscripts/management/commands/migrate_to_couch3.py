from django.core.management.base import BaseCommand
from cloudant.client import Cloudant


def sync_dbs(source_db_obj, destination_db_obj):
    for doc in source_db_obj:
        doc_obj = destination_db_obj.create_document(doc)
        if not doc_obj.exists():
            print(f'Unable to sync ${doc_obj._id} in ${destination_db_obj.database_name}')


class Command(BaseCommand):
    help = """Script to migrate local couchdb2 docs to couchdb3.
    It will iterate through all dbs sequentially and populate in couchdb3"""

    def handle(self, **options):
        couch_3_client = Cloudant('commcarehq', 'commcarehq', url='http://localhost:5984', connect=True)
        couch_2_client = Cloudant('', '', admin_party=True, url='http://localhost:5985', connect=True)
        old_dbs = couch_2_client.all_dbs()
        db_not_created = []
        for db_name in old_dbs:
            print(f'Copying db {db_name}')
            new_db_obj = couch_3_client.create_database(db_name)
            old_db_obj = couch_2_client[db_name]
            if not new_db_obj.exists():
                db_not_created.append(db_name)
            else:
                sync_dbs(old_db_obj, new_db_obj)
        print("Clearing out connection objects")
        couch_2_client.disconnect()
        couch_3_client.disconnect()
        print("Databases sucessfully migrated")
