from datetime import datetime

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.geospatial.utils import get_geo_case_property
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.document_stores import FormDocumentStore

FORM_ID_CHUNK_SIZE = 1000
CASE_BLOCK_CHUNK_SIZE = 100


class Command(BaseCommand):
    help = "Copy GPS coordinates from form metadata to case property"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--xmlns', required=False)
        parser.add_argument('--case-type', required=False)
        parser.add_argument(
            '--flag-multiple',
            action='store_true',
            help='Flag forms with multiple cases',
        )

    def handle(self, *args, **options):
        domain = options['domain']
        geo_case_property = get_geo_case_property(domain)

        latest_case_gps = {}
        case_blocks_chunk = []
        for form in iter_forms_with_location(domain, options.get('xmlns')):
            cases = get_form_cases(form, options.get('case_type'))
            if options['flag_multiple'] and len(cases) > 1:
                print(
                    f"Form {form['@id']} has multiple cases: "
                    f"{', '.join([case['@case_id'] for case in cases])}",
                    file=self.stderr,
                )
                continue

            for case in cases:
                gps_taken_at = as_datetime(form['meta']['timeStart'])
                if (
                    case['@case_id'] in latest_case_gps
                    and gps_taken_at < latest_case_gps[case['@case_id']]
                ):
                    # This form has an older location
                    continue

                latest_case_gps[case['@case_id']] = gps_taken_at
                case_block = get_case_block(
                    case['@case_id'],
                    geo_case_property,
                    form['meta']['location'],
                )
                case_blocks_chunk.append(case_block)
                if len(case_blocks_chunk) >= CASE_BLOCK_CHUNK_SIZE:
                    submit_chunk(domain, case_blocks_chunk)
                    case_blocks_chunk = []
        if case_blocks_chunk:
            submit_chunk(domain, case_blocks_chunk)


def iter_forms_with_location(domain, xmlns=None):
    doc_store = FormDocumentStore(domain, xmlns)
    doc_ids = doc_store.iter_document_ids()
    for doc_ids_chunk in chunked(doc_ids, FORM_ID_CHUNK_SIZE):
        for doc in doc_store.iter_documents(doc_ids_chunk):
            if doc['meta'].get('location'):
                yield doc


def get_form_cases(form, case_type=None):
    cases = []
    for case in form.get('case', []):
        if (
            case_type is None
            # Only "create" specifies case type
            or case.get('create', {}).get('case_type') == case_type
        ):
            cases.append(case)
    return cases


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
