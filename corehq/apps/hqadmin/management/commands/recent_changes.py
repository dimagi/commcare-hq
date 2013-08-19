from django.core.management.base import LabelCommand
from dimagi.utils.couch.database import get_db
from corehq.apps.hqadmin.history import get_recent_changes


class Command(LabelCommand):
    help = "Gets recent changes and prints them out in a csv format"
    args = "(number of changes)"
    label = ""

    def handle(self, *args, **options):
        limit = int(args[0]) if args else 500
        for row in get_recent_changes(get_db(), limit):
            print '{domain},{doc_type},{id},{rev}'.format(**row)
