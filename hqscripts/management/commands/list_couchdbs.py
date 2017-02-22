from __future__ import print_function
from django.core.management.base import BaseCommand
from corehq.util.couchdb_management import couch_config


class Command(BaseCommand):
    help = "List names of active couchdb dbs"
    args = ""
    label = ""

    def handle(self, *args, **options):
        for name in couch_config.all_dbs_by_db_name.keys():
            print(name)
