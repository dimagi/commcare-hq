import time
from django.core.management.base import BaseCommand

from corehq.apps.users.tasks import bulk_download_users_async
from corehq.apps.users.bulk_download import dump_users_and_groups


class Command(BaseCommand):
    help = "Kicks off a bulk user download and displays length of download"

    def add_arguments(self, parser):
        parser.add_argument(
            "domain"
        )
        parser.add_argument(
            "download_id"
        )
        parser.add_argument(
            "owner_id"
        )

    def handle(self, domain, download_id, owner_id, **options):
        start = time.perf_counter()
        user_filters = {
            'role_id': None,
            'search_string': '',
            'location_id': '',
            'selected_location_only': False,
            'user_active_status': None,
            'columns': 'all',
            'domains': [domain]
        }
        args = [domain, download_id, user_filters, bulk_download_users_async, owner_id]
        dump_users_and_groups(*args)
        end = time.perf_counter()
        print(f"Done in {end - start}")
