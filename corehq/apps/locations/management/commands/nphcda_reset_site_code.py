import re
from contextlib import contextmanager

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseBlock
from corehq.apps.es import CaseES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.models import CommCareCase

CASEBLOCK_CHUNKSIZE = 500
dry_run = False
verbose = False


class Command(BaseCommand):
    help = """
    Reset the site code of an NPHCDA Settlement location.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('location_id')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--verbose', action='store_true')

    def handle(self, domain, location_id, *args, **options):
        global dry_run
        global verbose

        dry_run = options['dry_run']
        verbose = options['verbose']

        location = get_location_by_id(domain, location_id)
        location.site_code = calc_site_code(location)
        if verbose:
            print(f"Setting {loc_str(location)} site code to '{location.site_code}'.")
        if not dry_run:
            location.save()

        with submit_case_block_coro(
            CASEBLOCK_CHUNKSIZE,
            domain,
            device_id=__name__
        ) as submit_case_block:
            cases = iter_cases(location)
            for case_block in update_cases_caseblocks(cases, location):
                submit_case_block.send(case_block)


def get_location_by_id(domain, location_id):
    return SQLLocation.objects.get(
        domain=domain,
        location_id=location_id,
    )


def loc_str(location):
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


def calc_site_code(location):
    ward = location.parent
    lga = ward.parent
    state = lga.parent
    return (
        f"{snake_case(location.name)}_"
        f"{snake_case(ward.name)}_"
        f"{snake_case(lga.name)}_"
        f"{snake_case(state.name)}_settlement"
    )


def snake_case(string):
    string = re.sub(r'[^\w\s]', ' ', string)
    string = re.sub(r'([A-Z])', r' \1', string)
    return re.sub(r'\s+', '_', string.strip().lower())


def iter_cases(location):
    iter_household_case_ids = (
        CaseES()
        .domain(location.domain)
        .case_type('household')
        .owner(location.location_id)
        .scroll_ids()
    )
    for case_id in iter_household_case_ids:
        household = CommCareCase.objects.get_case(case_id, location.domain)
        yield household
        for household_member in household.get_subcases():
            yield household_member


def update_cases_caseblocks(cases, location):
    for case in cases:
        yield CaseBlock(
            create=False,
            case_id=case.case_id,
            update={'settlement_code': location.site_code},
        ).as_text()


def coro_as_context(func):
    @contextmanager
    def wrapper(*args, **kwargs):
        coro = func(*args, **kwargs)
        next(coro)
        try:
            yield coro
        finally:
            coro.close()
    return wrapper


@coro_as_context
def submit_case_block_coro(chunk_size, *args, **kwargs):
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
