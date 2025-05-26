import csv

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from corehq.apps.es import CaseES
from corehq.apps.hqcase.utils import submit_case_blocks
from dimagi.utils.chunked import chunked

max_term_count = 500
case_block_count = 1000


class Command(BaseCommand):
    help = """
    Fixes ownership of cases from old location IDs to new location IDs.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('location_id_filename')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, domain, location_id_filename, *args, **options):
        id_map = get_deleted_id_to_new_id_map(location_id_filename)
        case_es_hits = iter_case_es_hits_with_deleted_owners(domain, id_map.keys())
        total_case_blocks = 0
        for case_es_hits_chunk in chunked(case_es_hits, case_block_count):
            case_blocks = [
                get_case_block_text(case_es_hit, id_map[case_es_hit['owner_id']])
                for case_es_hit in case_es_hits_chunk
            ]
            total_case_blocks += len(case_blocks)
            if options['dry_run']:
                self.stdout.write(f'Dry run: Total cases: {total_case_blocks}')
            else:
                submit_case_blocks(case_blocks, domain, device_id=__name__)
                self.stdout.write(f'Total cases updated: {total_case_blocks}')


def get_deleted_id_to_new_id_map(location_id_filename):
    """
    Returns a map of deleted location IDs to new location IDs.
    """
    with open(location_id_filename, 'r') as location_id_file:
        reader = csv.DictReader(location_id_file)
        return {row['deleted_id']: row['new_id'] for row in reader}


def iter_case_es_hits_with_deleted_owners(domain, deleted_ids):
    """
    Yields CaseES search hits where case owners are deleted locations.
    """
    for deleted_ids_chunk in chunked(deleted_ids, max_term_count, collection=list):
        for hit in CaseES().domain(domain).owner(deleted_ids_chunk).run().hits:
            yield hit


def get_case_block_text(case_es_hit, new_location_id):
    """
    Returns a case block to update a case with its new location ID.
    """
    update = {'settlement_id': new_location_id}
    if case_es_hit['type'] == 'household':
        update['choose_settlement'] = new_location_id
    return CaseBlock(
        create=False,
        case_id=case_es_hit['_id'],
        owner_id=new_location_id,
        update=update,
    ).as_text()
