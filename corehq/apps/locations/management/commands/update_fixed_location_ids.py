import csv

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xform import get_case_updates
from dimagi.utils.chunked import chunked

from corehq.apps.es import CaseES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.models import CommCareCase

SCRIPT_DEVICE_IDS = (
    'corehq.apps.locations.management.commands.update_owner_ids',
    'corehq.apps.locations.management.commands.update_location_ids',
)
MAX_TERM_COUNT = 500
CASE_BLOCK_COUNT = 1000


class Command(BaseCommand):
    help = """
    Fixes ownership of cases that were assigned the incorrect new location ID.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('location_id_filename')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, domain, location_id_filename, *args, **options):
        id_map = get_id_map(location_id_filename)
        case_es_hits = iter_case_es_hits(domain, id_map.keys())
        case_blocks = iter_case_blocks(case_es_hits, id_map)
        total_case_blocks = 0
        for case_blocks_chunk in chunked(case_blocks, CASE_BLOCK_COUNT):
            total_case_blocks += len(case_blocks_chunk)
            if options['dry_run']:
                self.stdout.write(f'Dry run: Total cases: {total_case_blocks}')
            else:
                submit_case_blocks(case_blocks_chunk, domain, device_id=__name__)
                self.stdout.write(f'Total cases updated: {total_case_blocks}')


def get_id_map(location_id_filename):
    """
    Returns a map of {'maybe wrong ID': {'deleted ID': 'new ID'}}.
    """
    with open(location_id_filename, 'r') as location_id_file:
        reader = csv.DictReader(location_id_file)
        # CSV columns:
        # * "id used by the first script": The ID based on the non-unique
        #   site code. Some (not all) cases will need to be corrected.
        # * "deleted_id": The ID of the deleted location
        # * "true location_id": The correct location ID
        return {
            row['id used by the first script']: {
                row['deleted_id']: row['true location_id'],
            }
            for row in reader
        }


def iter_case_es_hits(domain, owner_ids):
    """
    Yields CaseES search hits where case owners might be wrong.
    """
    for owner_ids_chunk in chunked(owner_ids, MAX_TERM_COUNT, collection=list):
        for hit in CaseES().domain(domain).owner(owner_ids_chunk).run().hits:
            yield hit


def iter_case_blocks(case_es_hits, id_map):
    for case_es_hit in case_es_hits:
        current_owner_id = case_es_hit['owner_id']
        deleted_location_id = get_previous_owner_id(case_es_hit)
        assert deleted_location_id, \
            f'No previous owner_id found for case {case_es_hit["_id"]}'
        correct_location_id = id_map[current_owner_id][deleted_location_id]
        if current_owner_id != correct_location_id:
            yield get_case_block_text(case_es_hit, correct_location_id)


def get_previous_owner_id(case_es_hit):
    """
    Navigates the case history of the case corresponding to 'case_es_hit',
    and returns 'owner_id' prior to the form submission with deviceID in
    SCRIPT_DEVICE_IDS
    """
    case = CommCareCase.wrap(case_es_hit)
    found = False  # Have we found the form that set the maybe-incorrect owner_id?
    transactions = sorted(case.get_form_transactions(), key=lambda t: t.server_date)
    for transaction in reversed(transactions):
        if not found:
            if transaction.device_id in SCRIPT_DEVICE_IDS:
                found = True
            continue

        xform_instance = transaction.form
        case_updates = get_case_updates(xform_instance, for_case=case.case_id)
        for case_update in case_updates:
            if 'owner_id' in case_update.create_block:
                return case_update.create_block['owner_id']
            if 'owner_id' in case_update.update_block:
                return case_update.update_block['owner_id']


def get_case_block_text(case_es_hit, new_location_id):
    """
    Returns a case block to update a case with its new location ID.
    """
    return CaseBlock(
        create=False,
        case_id=case_es_hit['_id'],
        owner_id=new_location_id,
        update={
            'settlement_id': new_location_id,
        },
    ).as_text()
