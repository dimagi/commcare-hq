import csv
import sys
from concurrent import futures

from django.core.management.base import BaseCommand

from corehq.apps.formplayer_api.sync_db import sync_db
from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    help = "Call the Formplayer API for each user in passed in CSV to force a sync."

    def add_arguments(self, parser):
        parser.add_argument('path', help='Path to CSV file. Columns "domain, username, as_user"')
        parser.add_argument('-t', '--threads', type=int, default=10, help='Number of threads to use.')

    def handle(self, path, **options):
        pool_size = options['threads']
        with open(path, 'r') as file:
            reader = csv.reader(file)

            results = []
            with futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
                row = next(reader)
                if row[0] != "domain":  # skip header
                    executor.submit(process_row, row)

                for row in reader:
                    executor.submit(process_row, row)

                futures.wait(results)


def process_row(row):
    domain, username, as_user = row
    user = CouchUser.get_by_username(username)
    if not user:
        sys.stderr.write(f"Row failure: unknown username: {','.join(row)}\n")
        return

    restore_as_user = None
    if as_user:
        restore_as_user = CouchUser.get_by_username(as_user)
        if not restore_as_user:
            sys.stderr.write(f"Row failure: unknown as_user: {','.join(row)}\n")

        if domain != restore_as_user.domain:
            sys.stderr.write(f"Row failure: domain mismatch with as_user: {','.join(row)}\n")

    try:
        sync_db(domain, username, restore_as_user)
    except Exception as e:
        sys.stderr.write(f"Row failure: {e}: {','.join(row)}\n")
