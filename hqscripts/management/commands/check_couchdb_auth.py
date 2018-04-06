from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.util.couchdb_management import couch_config


class Command(BaseCommand):
    help = "Check that localsettings are correct for authenticating to couchdb"

    def handle(self, **options):
        for slug, db in couch_config.all_dbs_by_slug.items():
            try:
                db.get_security()
            except Exception as e:
                print('DB access failed for "{}": {}'.format(slug, e))
            else:
                print('DB access OK for "{}"'.format(slug))
