import csv
import re
from contextlib import contextmanager
from typing import (
    Generator,
    Iterable,
    Iterator,
    NamedTuple,
    Optional,
    Protocol,
)

from django.core.management.base import BaseCommand, CommandError

import xlrd
from couchdbkit import ResourceConflict

from casexml.apps.case.mock import CaseBlock

from corehq.apps.es import CaseES, UserES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase

CASEBLOCK_CHUNKSIZE = 500
COUNTRY_ID = '8a5dd963b891448f87edbe8edb8dfc69'

code_to_location_id = {
    'sokoto·bodinga·bangi/dabaga': '7774758ed847495898330b137388c430',  # Bangi Dabaga
    'katsina·charanci': '783c7d1e95f745deaed46af70ea13969',  # Charanchi
    'zamfara·gummi·magai': '99526c8e94d1478f905a9039ed8bcb3d',  # Magaji
}
location_cache: dict[str, SQLLocation] = {}

verbose = False
dry_run = False


class SheetProto(Protocol):
    """
    Quacks like a xlrd.sheet.Sheet
    """
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


class LocationError(ValueError):
    pass


class LocationNotFoundError(LocationError):
    pass


class MultipleLocationsFoundError(LocationError):
    pass


class Settlement(NamedTuple):
    domain: str
    state_name: str
    lga_name: str
    ward_name: str
    settlement_name: str
    location_id: Optional[str]  # location_id is None for new locations

    def __str__(self):
        """
        Returns settlement_name, and location_id if set.

        >>> print(Settlement('', '', '', '', 'West End', None))
        West End
        >>> print(Settlement('', '', '', '', 'West End', 'abc123'))
        West End (abc123)

        """
        if self.location_id:
            return f"{self.settlement_name} ({self.location_id})"
        return self.settlement_name

    def __bool__(self):
        """
        True if anything but domain is set.

        >>> bool(Settlement('test-domain', '', '', '', '', None))
        False
        >>> bool(Settlement('test-domain', '', '', '', '', 'abc123'))
        True

        """
        return any((
            self.state_name,
            self.lga_name,
            self.ward_name,
            self.settlement_name,
            self.location_id,
        ))

    def get_location_or_none(self) -> Optional[SQLLocation]:
        try:
            return self.get_location()
        except LocationNotFoundError:
            return None
        # Fail hard on MultipleLocationsFoundError

    def get_location(self) -> SQLLocation:
        if self.location_id:
            return get_location_by_id(self.domain, self.location_id)
        ward = self.get_ward()
        settlement_code = self.get_settlement_code()
        return get_location_by_code(
            self.domain,
            settlement_code,
            ward.location_id,
            self.get_site_code(),
        )

    def get_ward(self):
        state_code = self.get_state_code()
        state = get_location_by_code(self.domain, state_code, COUNTRY_ID)
        lga_code = self.get_lga_code()
        lga = get_location_by_code(self.domain, lga_code, state.location_id)
        ward_code = self.get_ward_code()
        return get_location_by_code(self.domain, ward_code, lga.location_id)

    def get_state_code(self):
        return get_code(self.state_name)

    def get_lga_code(self):
        return get_code(self.state_name, self.lga_name)

    def get_ward_code(self):
        return get_code(self.state_name, self.lga_name, self.ward_name)

    def get_settlement_code(self):
        return get_code(
            self.state_name,
            self.lga_name,
            self.ward_name,
            self.settlement_name,
        )

    def get_site_code(self) -> str:
        """
        Generate a site code for a settlement.

        >>> settlement = Settlement(
        ...    domain='test-domain',
        ...    state_name='Sokoto',
        ...    lga_name='Bodinga',
        ...    ward_name='Bagarawa',
        ...    settlement_name='Agwarge',
        ...    location_id=None,
        ... )
        >>> settlement.get_site_code()
        'agwarge_bagarawa_bodinga_sokoto_settlement'

        """
        return (
            f"{snake_case(self.settlement_name)}_"
            f"{snake_case(self.ward_name)}_"
            f"{snake_case(self.lga_name)}_"
            f"{snake_case(self.state_name)}_settlement"
        )


class SettlementPair(NamedTuple):
    old_settlement: Settlement
    new_settlement: Settlement


class Command(BaseCommand):
    help = """
    Move mismatched users and their cases based on the output from
    the nphcda_find_mismatches management command.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-c', '--input-csv', type=str)
        parser.add_argument('-x', '--input-xls', type=str)
        parser.add_argument('--verbose', action='store_true')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--pre-check', action='store_true')

    def handle(self, domain, *args, **options):
        global verbose
        global dry_run

        if not only_one(
            options['input_csv'],
            options['input_xls'],
        ):
            raise CommandError('Please specify only one input file')
        elif options['input_csv']:
            all_settlement_pairs = load_csv(domain, options['input_csv'])
        elif options['input_xls']:
            all_settlement_pairs = load_xls(domain, options['input_xls'])
        else:
            raise CommandError('Must specify either input-csv or input-xls')

        verbose = options['verbose']
        dry_run = options['dry_run']

        if options['pre_check']:
            pre_check(all_settlement_pairs)
            self.stdout.write(self.style.SUCCESS('OK'))
            return

        with submit_case_block_coro(
            CASEBLOCK_CHUNKSIZE,
            domain,
            device_id=__name__
        ) as submit_case_block:
            for old_settlement, new_settlement in all_settlement_pairs:
                if new_location := new_settlement.get_location_or_none():
                    if new_location.location_id != old_settlement.location_id:
                        for user_id in iter_user_ids(old_settlement):
                            assign_location(user_id, new_location)
                    cases = iter_cases(old_settlement)
                    for case_block in move_cases_caseblocks(
                        cases,
                        new_location,
                        old_settlement,
                        new_settlement,
                    ):
                        submit_case_block.send(case_block)
                    if new_location.location_id != old_settlement.location_id:
                        delete_settlement(old_settlement)
                else:
                    location = old_settlement.get_location()
                    move_settlement(
                        location,
                        old_settlement,
                        new_settlement,
                    )
                    cases = iter_cases(old_settlement)
                    for case_block in update_cases_caseblocks(
                        cases,
                        location,
                        old_settlement,
                        new_settlement,
                    ):
                        submit_case_block.send(case_block)


def only_one(*args):
    """
    Returns True if only one of the arguments is truthy.

    >>> only_one('a', '', None)
    True
    >>> only_one('a', 'b', None)
    False

    """
    return sum(1 for arg in args if arg) == 1


def load_csv(domain: str, csv_filename: str) -> Iterator[SettlementPair]:
    """
    Yields UserChanges instances from the given CSV file.
    """
    sheet = CSVSheet(csv_filename)
    return load_sheet(domain, sheet)


def load_xls(domain: str, xls_filename: str) -> Iterator[SettlementPair]:
    """
    Yields UserChanges instances from the given Excel file (XLS format).
    """
    book = xlrd.open_workbook(xls_filename)
    sheet = book.sheet_by_index(0)
    return load_sheet(domain, sheet)


def load_sheet(domain: str, sheet: SheetProto) -> Iterator[SettlementPair]:
    for row in range(1, sheet.nrows):  # Skip the first row
        # Skip the first column (Username): Unused
        old_settlement = Settlement(
            domain=domain,
            state_name=sheet.cell_value(rowx=row, colx=1),
            lga_name=sheet.cell_value(rowx=row, colx=2),
            ward_name=sheet.cell_value(rowx=row, colx=3),
            settlement_name=sheet.cell_value(rowx=row, colx=4),
            location_id=sheet.cell_value(rowx=row, colx=5),
        )
        clean_name = one_space(sheet.cell_value(rowx=row, colx=9)).title()
        new_settlement = Settlement(
            domain=domain,
            state_name=sheet.cell_value(rowx=row, colx=6),
            lga_name=sheet.cell_value(rowx=row, colx=7),
            ward_name=sheet.cell_value(rowx=row, colx=8),
            settlement_name=clean_name,
            location_id=sheet.cell_value(rowx=row, colx=10) or None,
        )
        if old_settlement or new_settlement:  # Row is not blank
            if verbose:
                print(f'Processing {old_settlement!r}')
            yield SettlementPair(old_settlement, new_settlement)


def pre_check(settlement_pairs: Iterator[SettlementPair]) -> None:
    errors = []
    for old_settlement, new_settlement in settlement_pairs:
        if old_settlement.location_id in location_cache:
            errors.append(f'{old_settlement} has already been processed')
        try:
            # Check old location exists
            old_settlement.get_location()
        except Exception as err:
            errors.append(f'Current location {old_settlement!r}: {err}')
        try:
            # Check spelling of parent locations
            new_settlement.get_ward()
        except Exception as err:
            errors.append(f'New location {new_settlement!r} ward: {err}')
    if errors:
        raise CommandError('\n'.join(errors))


def get_location_by_code(
    domain: str,
    code: str,
    parent_location_id: str,
    site_code: Optional[str] = None,
) -> SQLLocation:
    # Modifies the value of code_to_location_id, location_cache
    if code in code_to_location_id:
        return get_location_by_id(domain, code_to_location_id[code])

    name = get_location_name(code)
    parent = get_location_by_id(domain, parent_location_id)
    locations = parent.children.filter(name__iexact=name).all()
    if len(locations) == 1:
        location = locations[0]
    elif len(locations) > 1:
        if site_code:
            location = select_location(locations, name, parent, site_code)
        else:
            raise MultipleLocationsFoundError(
                f"Multiple locations found for '{name}' under {loc_str(parent)}"
            )
    else:
        raise LocationNotFoundError(
            f"No location found for '{name}' under {loc_str(parent)}"
        )
    code_to_location_id[code] = location.location_id
    location_cache[location.location_id] = location
    return location


def get_location_by_id(domain: Optional[str], location_id: str) -> SQLLocation:
    # Modifies the value of location_cache

    if location_id not in location_cache:
        queryset = SQLLocation.objects.filter(location_id=location_id)
        if domain:
            queryset = queryset.filter(domain=domain)
        try:
            location_cache[location_id] = queryset.get()
        except SQLLocation.DoesNotExist as err:
            raise LocationNotFoundError(f'location_id {location_id} not found') from err
    return location_cache[location_id]


def select_location(
    locations: Iterable[SQLLocation],
    name: str,
    parent: SQLLocation,
    site_code: str,
) -> SQLLocation:
    locations = [loc for loc in locations if loc.site_code == site_code]
    if len(locations) == 1:
        return locations[0]
    raise MultipleLocationsFoundError(
        f"Multiple locations found for '{name}' under {loc_str(parent)}"
    )


def delete_settlement(settlement: Settlement) -> None:
    if verbose:
        print(f'Deleting settlement {settlement}')
    location = settlement.get_location()
    ward = get_location_by_id(settlement.domain, location.parent_location_id)
    if not dry_run:
        location.delete()
        if not ward.children.exists():
            if verbose:
                print(f'Deleting ward {loc_str(ward)}')
            ward.delete()


def iter_user_ids(settlement: Settlement) -> Iterator[str]:
    """
    Yields CommCareUser instances for the given location ID.
    """
    assert settlement.location_id
    return (
        UserES()
        .mobile_users()
        .domain(settlement.domain)
        .location(settlement.location_id)
        .scroll_ids()
    )


def assign_location(user_id: str, location: SQLLocation) -> None:
    user = CommCareUser.get_by_user_id(user_id, location.domain)
    if verbose:
        print(f'Assigning {user.raw_username} to {loc_str(location)}')
    if not dry_run:
        try:
            user.add_to_assigned_locations(location)
        except ResourceConflict:
            # Give the user another chance
            user = CommCareUser.get_by_user_id(user_id, location.domain)
            user.add_to_assigned_locations(location)
    # We don't need to unassign the user from the old settlement. That
    # will be done when we delete the location.


def move_settlement(
    location: SQLLocation,
    old_settlement: Settlement,
    new_settlement: Settlement,
) -> None:
    """
    Rename a settlement and/or move it to a new parent location.
    """
    if new_settlement.settlement_name != old_settlement.settlement_name:
        # Rename settlement
        if verbose:
            print(f'Renaming {old_settlement} to {new_settlement}')
        location.name = new_settlement.settlement_name

    if (
        new_settlement.lga_name != old_settlement.lga_name
        or new_settlement.ward_name != old_settlement.ward_name
    ):
        # Move settlement to new parent location
        if verbose:
            print(f'Moving {new_settlement} to {new_settlement.lga_name}, '
                  f'{new_settlement.ward_name}')
        location.parent = new_settlement.get_ward()

    location.site_code = new_settlement.get_site_code()
    if not dry_run:
        location.save()


def iter_cases(settlement: Settlement) -> Iterator[CommCareCase]:
    """
    Yields cases owned by settlement
    """
    assert settlement.location_id
    household_case_ids = (
        CaseES()
        .domain(settlement.domain)
        .case_type('household')
        .owner(settlement.location_id)
        .get_ids()
    )
    for case_id in household_case_ids:
        household = CommCareCase.objects.get_case(case_id, settlement.domain)
        yield household
        for household_member in household.get_subcases():
            yield household_member
            for subcase in household_member.get_subcases():
                yield subcase  # pregnancy, service, vaccine_doses cases


def move_cases_caseblocks(
    cases: Iterable[CommCareCase],
    location: SQLLocation,
    old_settlement: Settlement,
    new_settlement: Settlement,
) -> Iterator[str]:
    """
    Yields CaseBlocks as text to set owner_id and update location names
    and IDs in cases.
    """
    for case in cases:
        case_updates = get_case_updates(
            case,
            location,
            old_settlement,
            new_settlement,
        )
        case_updates.update(get_settlement_id_updates(case, location))
        yield CaseBlock(
            create=False,
            case_id=case.case_id,
            owner_id=location.location_id,
            update=case_updates,
        ).as_text()


def update_cases_caseblocks(
    cases: Iterable[CommCareCase],
    location: SQLLocation,
    old_settlement: Settlement,
    new_settlement: Settlement,
) -> Iterator[str]:
    """
    Yields CaseBlocks as text to update location names in cases.
    """
    for case in cases:
        case_updates = get_case_updates(
            case,
            location,
            old_settlement,
            new_settlement,
        )
        yield CaseBlock(
            create=False,
            case_id=case.case_id,
            update=case_updates,
        ).as_text()


def get_case_updates(
    case: CommCareCase,
    location: SQLLocation,
    old_settlement: Settlement,
    new_settlement: Settlement,
) -> dict[str, str]:
    case_updates = get_settlement_name_updates(case, location)
    if new_settlement.lga_name != old_settlement.lga_name:
        case_updates.update(get_lga_updates(case, location))
        case_updates.update(get_ward_updates(case, location))
    elif new_settlement.ward_name != old_settlement.ward_name:
        case_updates.update(get_ward_updates(case, location))
    return case_updates


def get_settlement_id_updates(
    case: CommCareCase,
    location: SQLLocation,
) -> dict[str, str]:
    settlement_id_updates = {'settlement_id': location.location_id}
    if case.type == 'household':
        settlement_id_updates.update({
            'choose_settlement': location.location_id,
        })
    return settlement_id_updates


def get_settlement_name_updates(
    case: CommCareCase,
    location: SQLLocation,
) -> dict[str, str]:
    if case.type in ('household', 'household_member'):
        return {
            'settlement_name': location.name,
            'settlement_code': location.site_code,
        }
    return {}


def get_lga_updates(
    case: CommCareCase,
    location: SQLLocation,
) -> dict[str, str]:
    ward = get_location_by_id(case.domain, location.parent_location_id)
    lga = get_location_by_id(case.domain, ward.parent_location_id)
    lga_updates = {'lga_id': lga.location_id}
    if case.type in ('household', 'household_member'):
        lga_updates.update({
            'lga_name': lga.name,
            'lga_code': lga.site_code,
        })
    return lga_updates


def get_ward_updates(
    case: CommCareCase,
    location: SQLLocation,
) -> dict[str, str]:
    ward = get_location_by_id(case.domain, location.parent_location_id)
    ward_updates = {
        'ward_id': ward.location_id,
    }
    if case.type in ('household', 'household_member'):
        ward_updates.update({
            'ward_name': ward.name,
            'ward_code': ward.site_code,
        })
    return ward_updates


def coro_as_context(func):
    """
    Decorator to transform a coroutine function into a context manager.

    The context manager primes the coroutine using next() when entering
    the context, and calls .close() when exiting the context.

    Usage::

        @coroutine
        def my_coro():
            try:
                while True:
                    x = yield
                    # process x
            except GeneratorExit:
                # cleanup

        with my_coro() as coro:
            coro.send(data)

    """
    @contextmanager
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        next(coro)  # Prime the coroutine
        try:
            yield coro
        finally:
            coro.close()
    return wrapper


@coro_as_context
def submit_case_block_coro(chunk_size: int, *args, **kwargs) -> Generator[None, str, None]:
    """
    Accepts case blocks and submits them in chunks of chunk_size
    """
    case_blocks = []
    try:
        while True:
            case_block = yield
            case_blocks.append(case_block)
            if len(case_blocks) >= chunk_size:
                chunk = case_blocks[:chunk_size]
                case_blocks = case_blocks[chunk_size:]
                if verbose:
                    print(f'Updating {len(chunk)} cases')
                if not dry_run:
                    submit_case_blocks(chunk, *args, **kwargs)
    except GeneratorExit:
        if case_blocks:
            if verbose:
                print(f'Updating {len(case_blocks)} cases')
            if not dry_run:
                submit_case_blocks(case_blocks, *args, **kwargs)


def loc_str(location: SQLLocation) -> str:
    """
    Get a string representation of a location.

    >>> loc_str(SQLLocation(
    ...     domain='test-domain',
    ...     name='Katsina',
    ...     location_id='abc123',
    ... ))
    'Katsina (abc123)'

    """
    return f"{location.name} ({location.location_id})"


def get_code(*args: str) -> str:
    """
    Get the code for a location from the names of its parent locations.

    >>> get_code('Katsina')
    'katsina'
    >>> get_code('Katsina', 'Faskari', 'Maigora')
    'katsina·faskari·maigora'

    """
    return '·'.join([one_space(name).lower() for name in args])


def get_location_name(code: str) -> str:
    """
    Get the name of a location from its code.

    >>> get_location_name('katsina')
    'Katsina'
    >>> get_location_name('katsina·faskari·maigora')
    'Maigora'

    """
    return code.split('·')[-1].capitalize()


def one_space(string: str) -> str:
    """
    Replace multiple spaces with a single space.

    >>> one_space(' FoO   BaR  ')
    'FoO BaR'

    """
    return re.sub(r'\s+', ' ', string).strip()


def snake_case(string: str) -> str:
    """
    Convert string to snake case.

    >>> snake_case('FooBar')
    'foo_bar'
    >>> snake_case('Foo Bar')
    'foo_bar'

    """
    # Replace non-alphanumeric characters with spaces
    string = re.sub(r'[^\w\s]', ' ', string)
    # Insert space before any capital in a word
    string = re.sub(r'([A-Z])', r' \1', string)
    # Convert to lowercase and replace spaces with underscores
    return re.sub(r'\s+', '_', string.strip().lower())
