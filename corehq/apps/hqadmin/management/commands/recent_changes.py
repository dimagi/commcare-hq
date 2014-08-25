from django.core.management.base import LabelCommand
from dimagi.utils.couch.database import get_db
from corehq.apps.hqadmin.history import download_changes


class Command(LabelCommand):
    help = "Gets recent changes and prints them out in a csv format"
    args = "(number of changes) (filename)"
    label = ""

    def handle(self, *args, **options):
        limit = int(args[0]) if args else 500
        file = args[1] if len(args) > 1 else 'database_changes.csv'
        with open(file, 'wb') as f:
            download_changes(get_db(), limit, f)
