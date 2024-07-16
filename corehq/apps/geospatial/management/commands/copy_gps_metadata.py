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

    def handle(self, *args, **options):
        domain = options['domain']
        xmlns = options.get('xmlns')
        case_type = options.get('case_type')
        geo_case_property = get_geo_case_property(domain)

        case_blocks_chunk = []
        for form in iter_forms_with_location(domain, xmlns):
            gps = form['meta']['location']
            for case in iter_form_cases(form, case_type):
                case_block = get_case_block(
                    case['@case_id'],
                    geo_case_property,
                    gps
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


def iter_form_cases(form, case_type=None):
    for case in form.get('case', []):
        if (
            case_type is None
            # Only "create" specifies case type
            or case.get('create', {}).get('case_type') == case_type
        ):
            yield case


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
