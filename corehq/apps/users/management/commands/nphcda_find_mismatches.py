import csv
import json
import re
from collections import namedtuple
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import zip_longest
from typing import Iterable, Optional, TypedDict

from django.core.management.base import BaseCommand

import xlwt

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser

ScriptCode = str
IDMap = dict[str, str]
IDList = list[str]


UserRow = namedtuple('UserRow', 'state lga ward settlement username')


@dataclass
class Location:
    id: str
    site_code: str
    dip_name: str
    script_code: ScriptCode


@dataclass
class UserSettlements:
    user: CommCareUser
    settlements: list[Location]


class UserChanges(TypedDict):
    username: str
    location_map: IDMap
    unmapped_old_locations: IDList
    unmapped_new_locations: IDList


class LocationError(ValueError):
    pass


class UserError(ValueError):
    pass


class UserLocationError(ValueError):
    pass


location_cache: dict[ScriptCode, Location] = {
    'nambia·foo·bar·baz': Location(
        id='def456',
        site_code='baz_bar_foo_settlement',
        dip_name='Baz',
        script_code='nambia·foo·bar·baz',
    ),
}


# No need to cache more than one user. They are repeated in consecutive rows.
last_commcare_user: Optional[CommCareUser] = None


country = Location(
    id='abc123',
    site_code='nambia',
    dip_name='Nambia',
    script_code='nambia',
)


class Command(BaseCommand):
    help = """
    Find mismatched users.

    Uses the data in the CSV file to find mobile workers in the domain
    who have been matched to the wrong location.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('users_csv')
        parser.add_argument('-o', '--output-xlsx', type=str)

    def handle(self, domain, users_csv, *args, **options):
        if options['output_xlsx']:
            with get_worksheet(options['output_xlsx']) as sheet:
                row_by_ref = [1]  # Allow `write_to_sheet` to increment by ref
                for user_changes in iter_all_user_changes(domain, users_csv):
                    write_to_sheet(sheet, row_by_ref, user_changes)
        else:
            for user_changes in iter_all_user_changes(domain, users_csv):
                self.stdout.write(json.dumps(user_changes, indent=4))


@contextmanager
def get_worksheet(xlsx_filename):
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet('User Location Changes')
    for col, heading in enumerate([
        'Username',
        'Map from old ID',
        'Map to new ID',
        'Unmapped old IDs',
        'Unmapped new IDs',
    ]):
        sheet.write(0, col, heading)
    try:
        yield sheet
    finally:
        workbook.save(xlsx_filename)


def iter_all_user_changes(domain: str, users_csv: str) -> Iterable[UserChanges]:
    for user_settlements in iter_user_settlements(domain, users_csv):
        if not has_changes(user_settlements):
            continue
        yield get_user_changes(domain, user_settlements)


def iter_user_settlements(
    domain: str,
    csv_filename: str
) -> Iterable[UserSettlements]:
    user_settlements = None
    for row in iter_user_rows(csv_filename):
        user = get_commcare_user(domain, row.username)
        state = get_location(domain, row.state, country)
        lga = get_location(domain, row.lga, state)
        ward = get_location(domain, row.ward, lga)
        settlement = get_location(domain, row.settlement, ward)
        if user_settlements is None:
            user_settlements = UserSettlements(user, [settlement])
        elif user_settlements.user.user_id != user.user_id:
            yield user_settlements
            user_settlements = UserSettlements(user, [settlement])
        else:
            user_settlements.settlements.append(settlement)
    if user_settlements is not None:
        yield user_settlements


def iter_user_rows(csv_filename: str) -> Iterable[UserRow]:
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

            yield UserRow(**{k.lower(): v for k, v in full_row.items()})
            last_full_row = full_row


def get_location(domain: str, name: str, parent: Location) -> Location:
    # Modifies the value of location_cache

    name = lower_one_space(name)
    script_code = f'{parent.script_code}·{name}'
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


def get_commcare_user(domain: str, row_username: str) -> CommCareUser:
    global last_commcare_user

    username = f'{row_username.lower()}@{domain}.commcarehq.org'
    if last_commcare_user is None or last_commcare_user.username != username:
        commcare_user = CommCareUser.get_by_username(username)
        if commcare_user is None:
            raise UserError(f"User '{row_username}' not found")
        if commcare_user.domain != domain:
            raise UserError(f"User '{row_username}' not in domain '{domain}'")
        last_commcare_user = commcare_user

    return last_commcare_user


def has_changes(user_settlements: UserSettlements) -> bool:
    assigned_location_ids = set(user_settlements.user.assigned_location_ids)
    settlement_ids = {loc.id for loc in user_settlements.settlements}
    return assigned_location_ids != settlement_ids


def get_user_changes(
    domain: str,
    user_settlements: UserSettlements,
) -> UserChanges:
    assigned_location_ids = set(user_settlements.user.assigned_location_ids)
    settlement_ids = {loc.id for loc in user_settlements.settlements}
    old_location_ids = assigned_location_ids - settlement_ids
    new_location_ids = settlement_ids - assigned_location_ids
    new_ids_by_dip_name = {
        lower_one_space(loc.dip_name): loc.id
        for loc in user_settlements.settlements
        if loc.id in new_location_ids
    }

    location_id_map = {}
    old_sql_locations = SQLLocation.objects.filter(
        domain=domain,
        location_id__in=old_location_ids,
    ).all()
    for sql_loc in old_sql_locations:
        if new_id := new_ids_by_dip_name.get(lower_one_space(sql_loc.name)):
            # DIP name for settlement matches name of old location
            location_id_map[sql_loc.location_id] = new_id
            old_location_ids.remove(sql_loc.location_id)
            new_location_ids.remove(new_id)

    return UserChanges(
        username=user_settlements.user.raw_username,
        location_map=location_id_map,
        unmapped_old_locations=list(old_location_ids),
        unmapped_new_locations=list(new_location_ids),
    )


def lower_one_space(string: str) -> str:
    """
    Lowercase a string and replace multiple spaces with a single space.

    >>> lower_one_space('FoO   BaR')
    'foo bar'

    """
    return re.sub(r'\s+', ' ', string).strip().lower()


def write_to_sheet(
    sheet: xlwt.Worksheet,
    row_by_ref: list[int],
    user_changes: UserChanges,
) -> None:
    rows = zip_longest(
        [user_changes['username']],
        user_changes['location_map'].keys(),
        user_changes['location_map'].values(),
        user_changes['unmapped_old_locations'],
        user_changes['unmapped_new_locations'],
        fillvalue='',
    )
    for row in rows:
        for col, value in enumerate(row):
            sheet.write(row_by_ref[0], col, value)
        row_by_ref[0] += 1
