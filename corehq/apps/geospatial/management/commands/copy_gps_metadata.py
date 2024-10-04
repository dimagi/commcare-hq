from datetime import datetime

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xform import extract_case_blocks

from corehq.apps.es import FormES
from corehq.apps.geospatial.utils import get_geo_case_property
from corehq.apps.hqcase.utils import submit_case_blocks

FORMS_CHUNK_SIZE = 1000
CASE_BLOCK_CHUNK_SIZE = 100


class Command(BaseCommand):
    help = 'Copy GPS coordinates from form metadata to case property'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--xmlns', required=False)
        parser.add_argument('--case-type', required=False)
        parser.add_argument(
            '--flag-multiple',
            action='store_true',
            help='Flag and skip forms with multiple cases',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        domain = options['domain']
        is_dry_run = options['dry_run']
        geo_case_property = get_geo_case_property(domain)

        latest_case_gps = {}
        case_blocks_chunk = []
        total_case_updates = 0
        for form in iter_forms_with_location(domain, options.get('xmlns')):
            cases = get_form_cases(form, options.get('case_type'))
            if options['flag_multiple'] and len(cases) > 1:
                print(
                    f"Form {form['@id']} has multiple cases: "
                    f"{', '.join([case['@case_id'] for case in cases])}",
                    file=self.stderr,
                )
                # To log output to STDERR, use
                #     $ ./manage.py copy_gps_metadata ... 2> errors.log
                continue

            for case in cases:
                gps_taken_at = as_datetime(form['meta']['timeStart'])
                if (
                    case['@case_id'] in latest_case_gps
                    and gps_taken_at < latest_case_gps[case['@case_id']]
                ):
                    # This form has an older location
                    continue

                total_case_updates += 1
                latest_case_gps[case['@case_id']] = gps_taken_at
                case_block = get_case_block(
                    case['@case_id'],
                    case_property=geo_case_property,
                    value=form_location(form),
                )
                case_blocks_chunk.append(case_block)
                if len(case_blocks_chunk) >= CASE_BLOCK_CHUNK_SIZE:
                    if not is_dry_run:
                        submit_chunk(domain, case_blocks_chunk)
                    case_blocks_chunk = []
        if case_blocks_chunk:
            if not is_dry_run:
                submit_chunk(domain, case_blocks_chunk)
        print(f'Submitted {total_case_updates} case updates')


def iter_forms_with_location(domain, xmlns=None):
    query = FormES().domain(domain).sort('received_on', desc=True)
    if xmlns:
        query = query.xmlns(xmlns)
    for es_form in query.scroll_ids_to_disk_and_iter_docs():
        try:
            location = form_location(es_form['form'])
        except ValueError:
            # WAT?! This form was not submitted by CommCare. Move along.
            continue
        if location:
            # For example values of `es_form['form']`, see
            # corehq/apps/geospatial/tests/test_copy_gps_metadata.py
            yield es_form['form']


def form_location(form):
    """
    Extracts the form's location.

    >>> form_location({'meta': {'location': {'#text': '12.345 67.890'}}})
    '12.345 67.890'
    >>> form_location({'meta': {'location': 'New York'}})
    'New York'
    >>> form_location({'meta': {'location': {'city': 'New York'}}})
    Traceback (most recent call last):
        ...
    ValueError: Invalid location: {'city': 'New York'}
    >>> form_location({'meta': {}}) is None
    True

    """
    location = form['meta'].get('location')
    if not location:
        return None
    try:
        return location['#text']
    except (KeyError, TypeError) as err:
        if isinstance(location, str):
            return location
        raise ValueError(f"Invalid location: {location!r}") from err


def get_form_cases(form, case_type=None):
    cases = extract_case_blocks(form)
    if case_type is None:
        return cases
    return [
        c for c in cases
        if c.get('create', {}).get('case_type') == case_type
    ]


def as_datetime(js_datetime_str):
    """
    Convert a JavaScript datetime string to a Python datetime object

    >>> as_datetime('2024-07-15T22:08:24.439433Z')
    datetime.datetime(2024, 7, 15, 22, 8, 24, 439433)
    >>> as_datetime('2024-07-15T22:08:24.439433+01:00')
    Traceback (most recent call last):
        ...
    ValueError: time data '2024-07-15T22:08:24.439433+01:00' does not match format '%Y-%m-%dT%H:%M:%S.%fZ'

    """
    return datetime.strptime(js_datetime_str, '%Y-%m-%dT%H:%M:%S.%fZ')


def get_case_block(case_id, case_property, value):
    return CaseBlock(
        case_id=case_id,
        create=False,
        update={case_property: value},
    )


def submit_chunk(domain, case_blocks):
    submit_case_blocks(
        [cb.as_text() for cb in case_blocks],
        domain,
        device_id='corehq.apps.geospatial...copy_gps_metadata',
    )
