from django.core.management.base import BaseCommand

from dimagi.utils.couch.database import get_db

from corehq.apps.hqadmin.history import download_changes


class Command(BaseCommand):
    help = "Gets recent changes and prints them out in a csv format"

    def add_arguments(self, parser):
        parser.add_argument(
            'limit',
            default=500,
            nargs='?',
            type=int,
        )
        parser.add_argument(
            'filename',
            default='database_changes.csv',
            nargs='?',
        )

    def handle(self, limit, filename, **options):
        with open(filename, 'wb') as f:
            download_changes(get_db(), limit, f)
