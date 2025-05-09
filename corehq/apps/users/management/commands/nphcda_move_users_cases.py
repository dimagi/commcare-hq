import csv
from typing import Generator, Iterable, Iterator, Protocol

from django.core.management.base import BaseCommand, CommandError

import xlrd
import yaml

from casexml.apps.case.mock import CaseBlock

from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import wrap_case_search_hit
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase

from .nphcda_find_mismatches import UserChanges, get_location

CASE_BLOCK_COUNT = 1000


class SheetProto(Protocol):
    nrows: int

    def cell_value(self, rowx: int, colx: int) -> str:
        ...


class CSVSheet:
    """
    Duck types xlrd.sheet.Sheet for CSV.
    """

    def __init__(self, csv_filename: str) -> None:
        with open(csv_filename) as csv_file:
            self._sheet = list(csv.reader(csv_file))
        self.nrows = len(self._sheet)

    def cell_value(self, rowx: int, colx: int) -> str:
        return self._sheet[rowx][colx]


class Command(BaseCommand):
    help = """
    Move mismatched users and their cases based on the output from
    the nphcda_find_mismatches management command.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-c', '--input-csv', type=str)
        parser.add_argument('-x', '--input-xls', type=str)
        parser.add_argument('-y', '--input-yaml', type=str)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, domain, *args, **options):
        if not only_one(
            options['input_csv'],
            options['input_xls'],
            options['input_yaml'],
        ):
            raise CommandError('Please specify only one input file')
        elif options['input_csv']:
            all_user_changes = load_csv(options['input_csv'])
        elif options['input_xls']:
            all_user_changes = load_xls(options['input_xls'])
        elif options['input_yaml']:
            all_user_changes = load_yaml(options['input_yaml'])
        else:
            raise CommandError('Must specify either input-xls or input-yaml')

        move_case_block = move_case_block_coro(domain, options['dry_run'])
        next(move_case_block)  # Prime the coroutine
        for user_changes in all_user_changes:
            user = get_user(domain, user_changes)
            move_user(user, user_changes, options['dry_run'])
            cases = iter_cases(domain, user, user_changes)
            for case_block in iter_case_blocks(domain, cases, user_changes):
                move_case_block.send(case_block)
        move_case_block.close()


def only_one(*args):
    """
    Returns True if only one of the arguments is truthy.

    >>> only_one('a', '', None)
    True
    >>> only_one('a', 'b', None)
    False

    """
    return sum(1 for arg in args if arg) == 1


def load_csv(csv_filename: str) -> Iterator[UserChanges]:
    """
    Yields UserChanges instances from the given CSV file.
    """
    sheet = CSVSheet(csv_filename)
    return load_sheet(sheet)


def load_xls(xls_filename: str) -> Iterator[UserChanges]:
    """
    Yields UserChanges instances from the given Excel file (XLS format).
    """
    book = xlrd.open_workbook(xls_filename)
    sheet = book.sheet_by_index(0)
    return load_sheet(sheet)


def load_sheet(sheet: SheetProto) -> Iterator[UserChanges]:
    col_username = 0
    col_map_from_id = 5
    col_map_to_id = 10
    col_unmapped_old_ids = 15
    col_unmapped_new_ids = 20

    last_username, user_changes = None, {}
    for row in range(1, sheet.nrows):
        username = sheet.cell_value(rowx=row, colx=col_username)
        if (
            username
            and username != last_username
            and last_username is not None
            and user_has_changes(user_changes)
        ):
            yield user_changes
        if username and username != last_username:
            last_username = username
            user_changes = UserChanges(
                username=username,
                location_map={},
                unmapped_old_locations=[],
                unmapped_new_locations=[],
            )
        if map_from_id := sheet.cell_value(rowx=row, colx=col_map_from_id):
            map_to_id = sheet.cell_value(rowx=row, colx=col_map_to_id)
            assert map_to_id
            user_changes['location_map'][map_from_id] = map_to_id
        if unmapped_old_id := sheet.cell_value(rowx=row, colx=col_unmapped_old_ids):
            user_changes['unmapped_old_locations'].append(unmapped_old_id)
        if unmapped_new_id := sheet.cell_value(rowx=row, colx=col_unmapped_new_ids):
            user_changes['unmapped_new_locations'].append(unmapped_new_id)
    if last_username is not None and user_has_changes(user_changes):
        yield user_changes


def load_yaml(yaml_filename: str) -> Iterator[UserChanges]:
    """
    Yields UserChanges instances from the given YAML file.
    """
    with open(yaml_filename) as yaml_file:
        for user_changes in yaml.safe_load_all(yaml_file):
            yield user_changes


def user_has_changes(user_changes: UserChanges) -> bool:
    """
    Returns True if the user has any changes to their location assignments.

    >>> user_changes = {
    ...     'location_map': {},
    ...     'unmapped_new_locations': [],
    ...     'unmapped_old_locations': [],
    ...     'username': 'fo/baz005',
    ... }
    >>> user_has_changes(user_changes)
    False

    """
    return bool(
        user_changes['location_map']
        or user_changes['unmapped_old_locations']
        or user_changes['unmapped_new_locations']
    )


def move_case_block_coro(domain: str, dry_run: bool) -> Generator[None, str, None]:
    """
    Accepts case blocks and submits them in chunks of CASE_BLOCK_COUNT
    """
    case_blocks = []
    try:
        while True:
            case_block = yield
            case_blocks.append(case_block)
            if len(case_blocks) >= CASE_BLOCK_COUNT:
                chunk = case_blocks[:CASE_BLOCK_COUNT]
                case_blocks = case_blocks[CASE_BLOCK_COUNT:]
                print(f'Moving {len(chunk)} cases')
                if not dry_run:
                    submit_case_blocks(chunk, domain, device_id=__name__)
    except GeneratorExit:
        if case_blocks:
            print(f'Moving {len(case_blocks)} cases')
            if not dry_run:
                submit_case_blocks(case_blocks, domain, device_id=__name__)


def get_user(domain: str, user_changes: UserChanges) -> CommCareUser:
    """
    Returns the CommCareUser for the username in user_changes.
    """
    username = f"{user_changes['username'].lower()}@{domain}.commcarehq.org"
    return CommCareUser.get_by_username(username)


def move_user(user: CommCareUser, user_changes: UserChanges, dry_run: bool) -> None:
    """
    user_changes represents the diff between the user's current location
    assignments, and those in the DIP Collation Workbook. Removes old
    locations from the user's assigned locations, and adds new locations.
    """
    old_location_ids = set(
        list(user_changes['location_map'].keys())
        + user_changes['unmapped_old_locations']
    )
    new_location_ids = set(
        list(user_changes['location_map'].values())
        + user_changes['unmapped_new_locations']
    )
    location_ids = (
        set(user.assigned_location_ids)
        - old_location_ids
        | new_location_ids
    )
    if user.location_id not in location_ids:
        user.location_id = None  # Prepare to reset primary location
    print(f'Moving {user.raw_username}')
    if not dry_run:
        user.reset_locations(list(location_ids))


def iter_cases(
    domain: str,
    user: CommCareUser,
    user_changes: UserChanges,
) -> Iterator[CommCareCase]:
    """
    Yields cases owned by mapped old location IDs
    """
    mapped_old_location_ids = list(user_changes['location_map'].keys())
    household_query = (
        CaseSearchES()
        .domain(domain)
        .case_type('household')
        .owner(mapped_old_location_ids)
        .case_property_query('user_userid', user.user_id)
    )
    for household_hit in household_query.run().hits:
        household = wrap_case_search_hit(household_hit)
        yield household
        for household_member in household.get_subcases():
            yield household_member
            for subcase in household_member.get_subcases():
                yield subcase  # pregnancy, service, vaccine_doses cases


def iter_case_blocks(
    domain: str,
    cases: Iterable[CommCareCase],
    user_changes: UserChanges
) -> Iterator[str]:
    """
    Yields case blocks where the old owner location has been mapped to
    the new location.
    """
    for case in cases:
        new_location_id = user_changes['location_map'][case.owner_id]
        yield get_case_block_text(
            domain,
            case,
            new_location_id,
        )


def get_case_block_text(
    domain: str,
    case: CommCareCase,
    settlement_id: str,
) -> str:
    """
    Returns case block text based on case.type.
    """
    settlement = get_location(domain, settlement_id)
    ward = get_location(domain, settlement.parent_location_id)
    lga = get_location(domain, ward.parent_location_id)
    state = get_location(domain, lga.parent_location_id)
    country = get_location(domain, state.parent_location_id)
    update = {
        'country_id': country.location_id,
        'state_id': state.location_id,
        'lga_id': lga.location_id,
        'ward_id': ward.location_id,
        'settlement_id': settlement_id,
    }
    if case.type in ('household', 'household_member'):
        update.update({
            'country_name': country.name,
            'country_code': country.site_code,
            'state_name': state.name,
            'state_code': state.site_code,
            'lga_name': lga.name,
            'lga_code': lga.site_code,
            'ward_name': ward.name,
            'ward_code': ward.site_code,
            'settlement_name': settlement.name,
            'settlement_code': settlement.site_code,
        })
    if case.type == 'household':
        update.update({
            'choose_settlement': settlement_id,
        })
    return CaseBlock(
        create=False,
        case_id=case.case_id,
        owner_id=settlement_id,
        update=update,
    ).as_text()
