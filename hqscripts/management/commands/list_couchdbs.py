from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.util.couchdb_management import couch_config


class Command(BaseCommand):
    help = "List names of active couchdb dbs"

    def handle(self, **options):
        for name in couch_config.all_dbs_by_db_name.keys():
            print(name)
