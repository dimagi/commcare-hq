import csv
import inspect
from argparse import RawTextHelpFormatter
from concurrent import futures
from datetime import datetime

import sys
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from corehq.apps.formplayer_api.exceptions import FormplayerResponseException
from corehq.apps.formplayer_api.sync_db import sync_db
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import format_username
from corehq.util.argparse_types import validate_integer
from corehq.util.log import with_progress_bar
from custom.covid.tasks import get_users_for_priming, get_prime_restore_user_params


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
        parser.add_argument('--last-synced-hours', action=validate_integer(gt=0, lt=169), default=48,
                            help='Match users who have synced within the given window. '
                                 'Defaults to 48 hours. Max = 168 (1 week).')
        parser.add_argument('--not-synced-hours', action=validate_integer(gt=0, lt=169), default=8,
                            help='Exclude users who have synced within the given window. '
                                 'Defaults to 8 hours. Max = 168 (1 week).')
        parser.add_argument('--min-cases', action=validate_integer(gt=0),
                            help='Match users with this many cases or more.')

        parser.add_argument('--limit', action=validate_integer(gt=0), help='Limit the number of users matched.')
        parser.add_argument('-t', '--threads', action=validate_integer(gt=0), default=10,
                            help='Number of threads to use.')
        parser.add_argument('--dry-run', action='store_true', help='Only print the list of users.')
        parser.add_argument('--dry-run-count', action='store_true', help='Only print the count of matched users.')
        parser.add_argument('--quiet', action='store_true', help='Only output error rows to stdout')

    def handle(self,
               from_csv=None,
               domains=None,
               last_synced_hours=None,
               not_synced_hours=None,
               min_cases=None,
               limit=None,
               **options
               ):
        pool_size = options['threads']
        dry_run = options['dry_run']
        dry_run_count = options['dry_run_count']
        quiet = options['quiet']

        validate = True
        if from_csv:
            users = _get_users_from_csv(from_csv)
            if dry_run_count:
                sys.stderr.write(f"\n{len(list(users))} users in CSV file '{from_csv}'\n")
                return
        else:
            domains = [domain.strip() for domain in domains if domain.strip()]
            synced_since = datetime.utcnow() - relativedelta(hours=last_synced_hours)
            not_synced_since = datetime.utcnow() - relativedelta(hours=not_synced_hours)
            if dry_run_count:
                users = list(_get_user_rows(domains, synced_since, not_synced_since, min_cases, limit))
                sys.stderr.write(f"\nMatched {len(users)} users for filters:\n")
                sys.stderr.write(f"\tDomains: {domains or '---'}\n")
                sys.stderr.write(f"\tSynced after: {synced_since}\n")
                sys.stderr.write(f"\tNot Synced after: {not_synced_since}\n")
                sys.stderr.write(f"\tMin cases: {min_cases or '---'}\n")
                sys.stderr.write(f"\tLimit: {limit or '---'}\n")
                return

            users = _get_users_from_db(domains, synced_since, not_synced_since, min_cases, limit)
            validate = False

        with futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
            sys.stderr.write("Spawning tasks\n")
            results = {executor.submit(process_row, user, validate, dry_run, quiet): user for user in users}

            for future in with_progress_bar(futures.as_completed(results), length=len(results), stream=sys.stderr):
                user = results[future]
                try:
                    future.result()
                except Exception as e:
                    _log_message(user, f"unexpected error: {e}", is_error=True)

        if not results:
            sys.stderr.write("\nNo users processed")


def _log_message(row, msg, is_error=True):
    status = 'ERROR' if is_error else 'SUCCESS'
    row_csv = ','.join(['' if f is None else f for f in row])
    sys.stdout.write(f'{row_csv},{status},"{msg}"\n')


def process_row(row, validate, dry_run, quiet):
    domain, username, as_user = row
    if validate:
        user = CouchUser.get_by_username(username)
        if not user:
            _log_message(row, "unknown username")
            return

        if as_user:
            as_username = format_username(as_user, domain) if '@' not in as_user else as_user
            restore_as_user = CouchUser.get_by_username(as_username)
            if not restore_as_user:
                _log_message(row, "unknown as_user")

            if domain != restore_as_user.domain:
                _log_message(row, "domain mismatch with as_user")

    if dry_run and not quiet:
        _log_message(row, "dry run success", is_error=False)
        return

    try:
        sync_db(domain, username, as_user or None)
    except FormplayerResponseException as e:
        _log_message(row, f"{e.response_json['exception']}")
    except Exception as e:
        _log_message(row, f"{e}")
    else:
        if not quiet:
            _log_message(row, "", is_error=False)


def _get_users_from_csv(path):
    with open(path, 'r') as file:
        reader = csv.reader(file)

        for row in reader:
            if not row or row == ["domain", "username", "as_user"]:  # skip header
                continue

            if len(row) != 3:
                _log_message(row, "Expected exactly 3 values in each row", True)
                continue

            yield row


def _get_user_rows(domains, synced_since, not_synced_since, min_cases, limit):
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


def _get_users_from_db(domains, synced_since, not_synced_since, min_cases, limit):
    rows = _get_user_rows(domains, synced_since, not_synced_since, min_cases, limit)
    for domain, request_user_id, as_user_id in rows:
        request_user, as_username = get_prime_restore_user_params(request_user_id, as_user_id)
        yield domain, request_user, as_username
