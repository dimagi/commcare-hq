import csv
import re
from collections import namedtuple
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Iterable, Optional, TypedDict

from django.core.management.base import BaseCommand

import xlwt
import yaml

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser

IDMap = dict[str, str]
IDList = list[str]


UserRow = namedtuple('UserRow', 'state lga ward settlement username')


@dataclass
class UserSettlements:
    user: CommCareUser
    settlements: list[SQLLocation]

    def has_changes(self) -> bool:
        assigned_location_ids = set(self.user.assigned_location_ids)
        settlement_ids = {loc.location_id for loc in self.settlements}
        return assigned_location_ids != settlement_ids


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


code_to_location_id = {
    'katsina·faskari·maigora': '24fc6b0f63af4cb1b8153d00e6a3ae1a',
}
location_cache: dict[str, SQLLocation] = {}


# No need to cache more than one user. They are repeated in consecutive rows.
last_commcare_user: Optional[CommCareUser] = None


country_id = '8a5dd963b891448f87edbe8edb8dfc69'


class Command(BaseCommand):
    help = """
    Find mismatched users.

    Uses the data in the CSV file to find mobile workers in the domain
    who have been matched to the wrong location.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('users_csv')
        parser.add_argument('-o', '--output-xls', type=str)

    def handle(self, domain, users_csv, *args, **options):
        if options['output_xls']:
            with get_worksheet(options['output_xls']) as sheet:
                row_by_ref = [1]  # Allow write_to_sheet() to increment by ref
                for user_changes in iter_all_user_changes(domain, users_csv):
                    write_to_sheet(sheet, row_by_ref, user_changes)
        else:
            all_user_changes = iter_all_user_changes(domain, users_csv)
            yaml.dump_all(all_user_changes, self.stdout)


def iter_all_user_changes(domain: str, users_csv: str) -> Iterable[UserChanges]:
    for user_settlements in iter_user_settlements(domain, users_csv):
        if not user_settlements.has_changes():
            continue
        yield get_user_changes(domain, user_settlements)


def iter_user_settlements(
    domain: str,
    csv_filename: str
) -> Iterable[UserSettlements]:
    user_settlements = None
    for row in iter_user_rows(csv_filename):
        user = get_commcare_user(domain, row.username)

        state_code = get_code(row.state)
        state = get_location_by_code(domain, state_code, country_id)

        lga_code = get_code(row.state, row.lga)
        lga = get_location_by_code(domain, lga_code, state.location_id)

        ward_code = get_code(row.state, row.lga, row.ward)
        ward = get_location_by_code(domain, ward_code, lga.location_id)

        settlement_code = get_code(row.state, row.lga, row.ward, row.settlement)
        settlement = get_location_by_code(domain, settlement_code, ward.location_id)

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
    """
    Iterates rows of csv_filename.

    Expected column names:
    - State
    - LGA
    - Ward
    - Settlement
    - Username

    """
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


def get_location_by_code(
    domain: str,
    code: str,
    parent_location_id: str,
) -> SQLLocation:
    # Modifies the value of code_to_location_id, location_cache
    if code in code_to_location_id:
        return get_location(domain, code_to_location_id[code])

    name = get_location_name(code)
    parent = get_location(domain, parent_location_id)
    locations = parent.children.filter(name__iexact=name).all()
    if len(locations) == 1:
        code_to_location_id[code] = locations[0].location_id
        location_cache[locations[0].location_id] = locations[0]
        return locations[0]
    elif len(locations) > 1:
        raise LocationError(f"Multiple locations found for '{name}' under {parent!r}")
    else:
        raise LocationError(f"No location found for '{name}' under {parent!r}")


def get_location(domain: Optional[str], location_id: str) -> SQLLocation:
    # Modifies the value of location_cache

    if location_id not in location_cache:
        queryset = SQLLocation.objects.filter(location_id=location_id)
        if domain:
            queryset = queryset.filter(domain=domain)
        location_cache[location_id] = queryset.get()
    return location_cache[location_id]


def iter_locations(
        domain: str,
        location_ids: Iterable[str],
) -> Iterable[SQLLocation]:
    # Modifies the value of location_cache

    cache_misses = []
    for location_id in location_ids:
        if location_id in location_cache:
            yield location_cache[location_id]
        else:
            cache_misses.append(location_id)
    for location in SQLLocation.objects.filter(
        domain=domain,
        location_id__in=cache_misses,
    ).all():
        location_cache[location.location_id] = location
        yield location


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


def get_user_changes(
    domain: str,
    user_settlements: UserSettlements,
) -> UserChanges:
    assigned_location_ids = set(user_settlements.user.assigned_location_ids)
    settlement_ids = {loc.location_id for loc in user_settlements.settlements}
    old_location_ids = assigned_location_ids - settlement_ids
    new_location_ids = settlement_ids - assigned_location_ids
    new_ids_by_name = {
        lower_one_space(loc.name): loc.location_id
        for loc in user_settlements.settlements
        if loc.location_id in new_location_ids
    }

    location_id_map = {}
    for loc in iter_locations(domain, list(old_location_ids)):
        if new_id := new_ids_by_name.get(lower_one_space(loc.name)):
            location_id_map[loc.location_id] = new_id
            old_location_ids.remove(loc.location_id)
            new_location_ids.remove(new_id)

    return UserChanges(
        username=user_settlements.user.raw_username,
        location_map=location_id_map,
        unmapped_old_locations=list(old_location_ids),
        unmapped_new_locations=list(new_location_ids),
    )


def get_code(*args: str) -> str:
    """
    Get the code for a location from the names of its parent locations.

    >>> get_code('Katsina')
    'katsina'
    >>> get_code('Katsina', 'Faskari', 'Maigora')
    'katsina·faskari·maigora'

    """
    return '·'.join([lower_one_space(name) for name in args])


def get_location_name(code: str) -> str:
    """
    Get the name of a location from its code.

    >>> get_location_name('katsina')
    'Katsina'
    >>> get_location_name('katsina·faskari·maigora')
    'Maigora'

    """
    return code.split('·')[-1].capitalize()


def lower_one_space(string: str) -> str:
    """
    Lowercase a string and replace multiple spaces with a single space.

    >>> lower_one_space('FoO   BaR')
    'foo bar'

    """
    return re.sub(r'\s+', ' ', string).strip().lower()


@contextmanager
def get_worksheet(xls_filename):
    heading = xlwt.XFStyle()
    heading.font.height = 0x00DC  # 220 (11pt)
    heading.font.bold = True

    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet('User Location Changes')
    sheet.write(0, 0, 'Username', style=heading)
    sheet.write_merge(0, 0, 1, 5, 'Map from old location', style=heading)
    sheet.write_merge(0, 0, 6, 10, 'Map to new location', style=heading)
    sheet.write_merge(0, 0, 11, 15, 'Unmapped old locations', style=heading)
    sheet.write_merge(0, 0, 16, 20, 'Unmapped new locations', style=heading)
    try:
        yield sheet
    finally:
        workbook.save(xls_filename)


def write_to_sheet(
    sheet: xlwt.Worksheet,
    row_by_ref: list[int],
    user_changes: UserChanges,
) -> None:
    for row in user_changes_to_rows(user_changes):
        for col, value in enumerate(row):
            sheet.write(row_by_ref[0], col, value)
        row_by_ref[0] += 1


def user_changes_to_rows(user_changes: UserChanges) -> Generator[list, None, None]:
    num_rows = max(
        1,
        len(user_changes['location_map']),
        len(user_changes['unmapped_old_locations']),
        len(user_changes['unmapped_new_locations']),
    )
    map_from = (loc_id for loc_id in user_changes['location_map'].keys())
    map_to = (loc_id for loc_id in user_changes['location_map'].values())
    old_ids = (loc_id for loc_id in user_changes['unmapped_old_locations'])
    new_ids = (loc_id for loc_id in user_changes['unmapped_new_locations'])
    for i in range(num_rows):
        row = [
            user_changes['username'] if i == 0 else ''
        ]
        row.extend(settlement_columns(next(map_from, None)))
        row.extend(settlement_columns(next(map_to, None)))
        row.extend(settlement_columns(next(old_ids, None)))
        row.extend(settlement_columns(next(new_ids, None)))
        yield row


def settlement_columns(settlement_id: Optional[str]) -> tuple:
    if settlement_id is None:
        return '', '', '', '', ''
    settlement = location_cache[settlement_id]
    ward = get_location(None, settlement.parent_location_id)
    lga = get_location(None, ward.parent_location_id)
    state = get_location(None, lga.parent_location_id)
    return (
        state.name,
        lga.name,
        ward.name,
        settlement.name,
        settlement_id,
    )
