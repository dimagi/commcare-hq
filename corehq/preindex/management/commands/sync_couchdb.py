from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Copy temporary design docs over existing ones'

    def handle(self, *args, **options):
        call_command('sync_prepare_couchdb_multi')
        call_command('sync_finish_couchdb_hq')
