import csv
import re
from collections import namedtuple
from typing import Iterable, Optional, TypedDict

from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser

Location = namedtuple('Location', 'id site_code dip_name script_code')
country = Location(
    id='abc123',
    site_code='nambia',
    dip_name='Nambia',
    script_code='nambia',
)
location_cache: dict[str, Location] = {
    'nambia|foo|bar|baz': Location(
        id='def456',
        site_code='baz_bar_foo_settlement',
        dip_name='Baz',
        script_code='nambia|foo|bar|baz',
    ),
}


UserRecord = namedtuple('UserRecord', 'state lga ward settlement username')
# No need to cache more than one user. They are repeated on consecutive rows.
last_commcare_user: Optional[CommCareUser] = None


UserCorrection = TypedDict('UserCorrection', {
    'username': str,
    'user_id': str,
    'location_codes': list[str],
})
last_correction: Optional[UserCorrection] = None


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
        global last_correction

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
                if last_correction is None:
                    self.stdout.write(user_import_headers)
                    last_correction = err.correction
                elif last_correction['username'] == err.correction['username']:
                    last_correction['location_codes'].extend(
                        err.correction['location_codes']
                    )
                else:
                    row = get_user_import_row(last_correction)
                    self.stdout.write(row)
                    last_correction = err.correction

        if last_correction is not None:
            row = get_user_import_row(last_correction)
            self.stdout.write(row)


def iter_users(csv_filename: str) -> Iterable[UserRecord]:
    username_re = re.compile(r'^[A-Z]{2}/[A-Z]{3}[0-9]+$')
    last_full_row = {}
    with open(csv_filename, 'r') as csv_file:
        for row in csv.DictReader(csv_file):
            # Skip rows where the Settlement value is blank
            if not row['Settlement']:
                continue
            # Replace blank values with their previous value
            full_row = {
                k: v if v else last_full_row[k]
                for k, v in row.items()
            }
            # Fix abbreviated Username value
            if (
                not username_re.match(full_row['Username'])
                and last_full_row['Username'].endswith(full_row['Username'])
            ):
                full_row['Username'] = last_full_row['Username']

            yield UserRecord(**{k.lower(): v for k, v in full_row.items()})
            last_full_row = full_row


def get_location(domain: str, name: str, parent: Location) -> Location:
    # Modifies the value of location_cache

    script_code = f'{parent.script_code}|{name.lower()}'
    if script_code not in location_cache:
        sql_parent = SQLLocation.objects.get(domain=domain, location_id=parent.id)
        sql_locations = sql_parent.children.filter(name__iexact=name).all()
        if len(sql_locations) == 1:
            location_cache[script_code] = Location(
                id=sql_locations[0].location_id,
                site_code=sql_locations[0].site_code,
                dip_name=name,
                script_code=script_code,
            )
        elif len(sql_locations) > 1:
            raise LocationError(f"Multiple locations found for '{name}' under {parent!r}")
        else:
            raise LocationError(f"No location found for '{name}' under {parent!r}")

    return location_cache[script_code]


def get_commcare_user(domain: str, user: UserRecord) -> CommCareUser:
    global last_commcare_user

    username = f'{user.username.lower()}@{domain}.commcarehq.org'
    if last_commcare_user is None or last_commcare_user.username != username:
        commcare_user = CommCareUser.get_by_username(username)
        if commcare_user is None:
            raise UserError(f"User '{user.username}' not found")
        if commcare_user.domain != domain:
            raise UserError(f"User '{user.username}' not in domain '{domain}'")
        last_commcare_user = commcare_user

    return last_commcare_user


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
            'location_codes': [settlement.site_code],
        })
        raise UserLocationError(
            correction,
            f"User '{user.username}' not in settlement '{settlement!r}'"
        )


user_import_headers = ','.join(
    ['username', 'user_id']
    + [f'location_code {i}' for i in range(1, 9)]
)


def get_user_import_row(correction: UserCorrection) -> str:
    location_codes = correction['location_codes']
    # Pad with empty strings
    location_codes += [''] * (8 - len(correction['location_codes']))
    return ','.join([
        correction['username'],
        correction['user_id'],
    ] + location_codes)
