import csv
import re
from collections import namedtuple
from typing import Iterable, TypedDict

from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser


Location = namedtuple('Location', 'id name code')
country = Location('abc123', 'Nambia', 'nambia')
location_cache = {
    'nambia|foo|bar|baz': 'def456',
}


UserRecord = namedtuple('UserRecord', 'state lga ward settlement username')
user_cache = {}


UserCorrection = TypedDict('UserCorrection', {
    'username': str,
    'user_id': str,
    'location_id 1': str,
})


class LocationError(ValueError):
    pass


class UserError(ValueError):
    pass


class UserLocationError(Exception):
    def __init__(self, correction: UserCorrection, *args, **kwargs):
        self.correction = correction
        super().__init__(*args, **kwargs)


class Command(BaseCommand):
    help = """
    Find mismatched users.

    Uses the data in the CSV file to find mobile workers in the domain
    who have been matched to the wrong location.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('users_csv')

    def handle(self, domain, users_csv, *args, **options):
        self.stdout.write('username,user_id,location_id 1')
        for user in iter_users(users_csv):
            # Find location
            try:
                state = get_location(domain, user.state, country)
                lga = get_location(domain, user.lga, state)
                ward = get_location(domain, user.ward, lga)
                settlement = get_location(domain, user.settlement, ward)
            except LocationError as err:
                self.stderr.write(str(err))
                continue

            # Output corrections
            try:
                confirm_user_location(domain, user, settlement)
            except UserError as err:
                self.stderr.write(str(err))
                continue
            except UserLocationError as err:
                row = ','.join([
                    err.correction['username'],
                    err.correction['user_id'],
                    err.correction['location_id 1'],
                ])
                self.stdout.write(row)


def iter_users(csv_filename: str) -> Iterable[UserRecord]:
    username_re = re.compile(r'^[A-Z]{2}/[A-Z]{3}[0-9]+$')
    last_full_row = {}
    with open(csv_filename, 'r') as csv_file:
        for row in csv.DictReader(csv_file):
            # Skip blank rows
            if not any(v for v in row.values()):
                continue
            # Replace blank values with their previous value
            full_row = {
                k: v if v else last_full_row[k]
                for k, v in row.items()
            }
            # Fix username
            if (
                not username_re.match(full_row['Username'])
                and last_full_row['Username'].endswith(full_row['Username'])
            ):
                full_row['Username'] = last_full_row['Username']

            yield UserRecord(**{k.lower(): v for k, v in full_row.items()})
            last_full_row = full_row


def get_location(domain: str, name: str, parent: Location) -> Location:
    code = f'{parent.code}|{name.lower()}'
    if code not in location_cache:
        sql_parent = SQLLocation.objects.get(domain=domain, location_id=parent.id)
        sql_locations = sql_parent.children.filter(name__iexact=name).all()
        if len(sql_locations) == 1:
            location_cache[code] = sql_locations[0].location_id
        elif len(sql_locations) > 1:
            raise LocationError(f"Multiple locations found for '{name}' under {parent!r}")
        else:
            raise LocationError(f"No location found for '{name}' under {parent!r}")

    return Location(location_cache[code], name, code)


def get_commcare_user(domain: str, user: UserRecord) -> CommCareUser:
    if user.username not in user_cache:
        full_username = f'{user.username.lower()}@{domain}.commcarehq.org'
        commcare_user = CommCareUser.get_by_username(full_username)
        if commcare_user is None:
            raise UserError(f"User '{user.username}' not found")
        if commcare_user.domain != domain:
            raise UserError(f"User '{user.username}' not in domain '{domain}'")
        user_cache[user.username] = commcare_user

    return user_cache[user.username]


def confirm_user_location(
    domain: str,
    user: UserRecord,
    settlement: Location,
) -> None:
    commcare_user = get_commcare_user(domain, user)
    if settlement.id not in commcare_user.assigned_location_ids:
        correction = UserCorrection(**{
            'username': commcare_user.username,
            'user_id': commcare_user.user_id,
            'location_id 1': settlement.id,
        })
        raise UserLocationError(
            correction,
            f"User '{user.username}' not in settlement '{settlement!r}'"
        )
