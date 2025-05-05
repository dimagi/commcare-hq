from typing import Generator, Iterable, Iterator

from django.core.management.base import BaseCommand, CommandError

import xlrd
import yaml

from casexml.apps.case.mock import CaseBlock

from corehq.apps.es import CaseSearchES
from corehq.apps.es.case_search import wrap_case_search_hit
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase

from .nphcda_find_mismatches import UserChanges

CASE_BLOCK_COUNT = 1000


location_cache = {}


class Command(BaseCommand):
    help = """
    Move mismatched users and their cases based on the output from
    the nphcda_find_mismatches management command.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-x', '--input-xls', type=str)
        parser.add_argument('-y', '--input-yaml', type=str)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, domain, *args, **options):
        if options['input_yaml'] and options['input_xls']:
            raise CommandError('Cannot specify both input-xls and input-yaml')
        elif options['input_xls']:
            all_user_changes = load_xls(options['input_xls'])
        elif options['input_yaml']:
            all_user_changes = load_yaml(options['input_yaml'])
        else:
            raise CommandError('Must specify either input-xls or input-yaml')
        move_case_block = move_case_block_coro(domain, options['dry_run'])
        for user_changes in all_user_changes:
            user = get_user(domain, user_changes)
            move_user(user, user_changes, options['dry_run'])
            cases = iter_cases(domain, user, user_changes)
            for case_block in iter_case_blocks(domain, cases, user_changes):
                move_case_block.send(case_block)
        move_case_block.close()


def load_xls(xls_filename: str) -> Iterator[UserChanges]:
    """
    Yields UserChanges instances from the given Excel file (XLS format).
    """
    book = xlrd.open_workbook(xls_filename)
    sheet = book.sheet_by_index(0)

    col_username = 0
    col_map_from_id = 5
    col_map_to_id = 10
    col_unmapped_old_ids = 15
    col_unmapped_new_ids = 20

    last_username, user_changes = None, {}
    for row in range(1, sheet.nrows):
        username = sheet.cell_value(rowx=row, colx=col_username)
        if username and username != last_username and last_username is not None:
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
            user_changes['unmapped_old_locations'].append(unmapped_new_id)
    if last_username is not None:
        yield user_changes


def load_yaml(yaml_filename: str) -> Iterator[UserChanges]:
    """
    Yields UserChanges instances from the given YAML file.
    """
    with open(yaml_filename) as yaml_file:
        for user_changes in yaml.safe_load_all(yaml_file):
            yield user_changes


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
        if case.type in ('household', 'household_member'):
            yield get_household_case_block_text(
                domain,
                case,
                new_location_id,
            )
        else:
            yield get_vaccine_doses_case_block_text(
                domain,
                case,
                new_location_id,
            )


def get_household_case_block_text(
    domain: str,
    case: CommCareCase,
    settlement_id: str,
) -> str:
    """
    Returns case block text for household and household_member cases.
    """
    settlement = get_location(domain, settlement_id)
    ward = get_location(domain, settlement.parent_location_id)
    lga = get_location(domain, ward.parent_location_id)
    state = get_location(domain, lga.parent_location_id)
    country = get_location(domain, state.parent_location_id)
    return CaseBlock(
        create=False,
        case_id=case.case_id,
        owner_id=settlement_id,
        update={
            'country_id': country.location_id,
            'country_name': country.name,
            'country_code': country.site_code,

            'state_id': state.location_id,
            'state_name': state.name,
            'state_code': state.site_code,

            'lga_id': lga.location_id,
            'lga_name': lga.name,
            'lga_code': lga.site_code,

            'ward_id': ward.location_id,
            'ward_name': ward.name,
            'ward_code': ward.site_code,

            'settlement_id': settlement_id,
            'settlement_name': settlement.name,
            'settlement_code': settlement.site_code,

            'location_id': settlement_id,
        },
    ).as_text()


def get_vaccine_doses_case_block_text(
    domain: str,
    case: CommCareCase,
    settlement_id: str,
) -> str:
    """
    Returns case block text for pregnancy, service and vaccine_doses cases.
    """

    settlement = get_location(domain, settlement_id)
    ward = get_location(domain, settlement.parent_location_id)
    lga = get_location(domain, ward.parent_location_id)
    state = get_location(domain, lga.parent_location_id)
    country = get_location(domain, state.parent_location_id)
    return CaseBlock(
        create=False,
        case_id=case.case_id,
        owner_id=settlement_id,
        update={
            'country_id': country.location_id,
            'state_id': state.location_id,
            'lga_id': lga.location_id,
            'ward_id': ward.location_id,
            'settlement_id': settlement_id,
        },
    ).as_text()


def get_location(domain: str, location_id: str) -> SQLLocation:
    """
    Returns the cached SQLLocation for the given location_id, and
    fetches from the database if not already cached.
    """
    if location_id not in location_cache:
        location_cache[location_id] = SQLLocation.objects.get(
            domain=domain,
            location_id=location_id,
        )
    return location_cache[location_id]
