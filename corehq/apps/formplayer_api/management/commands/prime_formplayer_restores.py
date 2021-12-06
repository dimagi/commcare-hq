import csv
import inspect
import sys
from argparse import RawTextHelpFormatter
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from corehq.apps.users.models import CouchUser
from corehq.util.argparse_types import validate_range
from custom.covid.tasks import get_users_for_priming, get_prime_restore_user_params, prime_formplayer_db_for_user


class Command(BaseCommand):
    help = inspect.cleandoc(
        """Call the Formplayer sync API for users from CSV or matching criteria.
        Usage:

        Redirect stdout to file to allow viewing progress bar:
        %(prog)s [args] > output.csv

        ### With users in a CSV file ###

        CSV Columns: "domain, username, as_user"

        %(prog)s --from-csv path/to/users.csv

        ### Query DB for users ###

        %(prog)s --domains a b c --last-synced-days 2 --min-cases 500 --limit 1000

        Use "--dry-run" and "--dry-run-count" to gauge impact of command.
        """
    )

    def create_parser(self, *args, **kwargs):
        # required to get nice output from `--help`
        parser = super(Command, self).create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument('--from-csv',
                            help='Path to CSV file. Columns "domain, username, as_user". When this is supplied '
                                 'only users in this file will be synced.')

        parser.add_argument('--domains', nargs='+', help='Match users in these domains.')
        parser.add_argument('--last-synced-hours', type=int, action=validate_range(gt=0, lt=673), default=48,
                            help='Match users who have synced within the given window. '
                                 'Defaults to %(default)s hours. Max = 673 (4 weeks).')
        parser.add_argument('--not-synced-hours', type=int, action=validate_range(gt=-1, lt=169),
                            help='Exclude users who have synced within the given window. '
                                 'Max = 168 (1 week).')
        parser.add_argument('--min-cases', type=int, action=validate_range(gt=0),
                            help='Match users with this many cases or more.')

        parser.add_argument('--limit', type=int, action=validate_range(gt=0),
                            help='Limit the number of users matched.')
        parser.add_argument('--dry-run', action='store_true', help='Only print the list of users.')
        parser.add_argument('--dry-run-count', action='store_true', help='Only print the count of matched users.')
        parser.add_argument('--clear-user-data', action='store_true',
                            help='Clear user data prior to performing sync.')

    def handle(self,
               from_csv=None,
               domains=None,
               last_synced_hours=None,
               not_synced_hours=None,
               min_cases=None,
               limit=None,
               **options
               ):
        dry_run = options['dry_run']
        dry_run_count = options['dry_run_count']
        clear_user_data = options['clear_user_data']

        if from_csv:
            users = _get_users_from_csv(from_csv)
            if dry_run_count:
                sys.stderr.write(f"\n{len(list(users))} users in CSV file '{from_csv}'\n")
                return

            for domain, request_user, as_username in users:
                request_user_id = CouchUser.get_by_username(request_user).user_id
                as_user_id = None
                if as_username:
                    as_user_id = CouchUser.get_by_username(as_username).user_id
                sys.stdout.write(f"{domain},{request_user},{request_user_id},{as_username},{as_user_id}\n")
                if not dry_run:
                    prime_formplayer_db_for_user.delay(
                        domain, request_user_id, as_user_id, clear_data=clear_user_data
                    )
        else:
            domains = [domain.strip() for domain in domains if domain.strip()]
            synced_since = datetime.utcnow() - relativedelta(hours=last_synced_hours)
            not_synced_since = (
                datetime.utcnow() - relativedelta(hours=not_synced_hours)
                if not_synced_hours else None
            )
            if dry_run_count:
                users = list(_get_user_rows(domains, synced_since, not_synced_since, min_cases, limit))
                sys.stderr.write(f"\nMatched {len(users)} users for filters:\n")
                sys.stderr.write(f"\tDomains: {domains or '---'}\n")
                sys.stderr.write(f"\tSynced after: {synced_since}\n")
                sys.stderr.write(f"\tNot Synced after: {not_synced_since}\n")
                sys.stderr.write(f"\tMin cases: {min_cases or '---'}\n")
                sys.stderr.write(f"\tLimit: {limit or '---'}\n")
                return

            users = _get_user_rows(domains, synced_since, not_synced_since, min_cases, limit)

            for domain, request_user_id, as_user_id in users:
                request_user, as_username = get_prime_restore_user_params(request_user_id, as_user_id)
                sys.stdout.write(f"{domain},{request_user},{request_user_id},{as_username},{as_user_id}\n")
                if not dry_run:
                    prime_formplayer_db_for_user.delay(
                        domain, request_user_id, as_user_id, clear_data=clear_user_data
                    )


def _get_users_from_csv(path):
    with open(path, 'r') as file:
        reader = csv.reader(file)

        for row in reader:
            if not row or row == ["domain", "username", "as_user"]:  # skip header
                continue

            if len(row) != 3:
                row_csv = ','.join(['' if f is None else f for f in row])
                sys.stdout.write(f'{row_csv},ERROR,"Expected exactly 3 values in each row"\n')
                continue

            yield row


def _get_user_rows(domains, synced_since, not_synced_since=None, min_cases=None, limit=None):
    remaining_limit = limit
    for domain in domains:
        if remaining_limit is not None and remaining_limit <= 0:
            break
        users = get_users_for_priming(domain, synced_since, not_synced_since, min_cases)
        if remaining_limit:
            users = users[:remaining_limit]
            remaining_limit -= len(users)
        for row in users:
            yield (domain, *row)
