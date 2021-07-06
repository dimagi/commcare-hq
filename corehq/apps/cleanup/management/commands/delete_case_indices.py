import csv
import logging
from collections import defaultdict

from attr import attrs, attrib
from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

logger = logging.getLogger("delete_case_indices")


@attrs
class CaseMeta:
    domain = attrib()
    case_id = attrib()
    referenced_type = attrib()
    referenced_id = attrib()
    index_identifier = attrib()


class Command(BaseCommand):
    help = 'Remove case indices from cases'

    def add_arguments(self, parser):
        parser.add_argument(
            'cases_csv_file',
            help="Columns: domain, case_id, referenced_id, index_identifier, referenced_type (optional)"
        )
        parser.add_argument('--username', help="Username to submit the forms with")
        parser.add_argument('--dry-run', action="store_true", help="Don't actually make the changes")

    def handle(self, cases_csv_file, **options):
        self.dry_run = options["dry_run"]
        self.username = options.get("username") or None

        case_metas = {}
        case_ids_by_domain = defaultdict(list)
        with open(cases_csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                case_id = row["case_id"]
                domain = row["domain"]
                case_metas[case_id] = CaseMeta(
                    domain,
                    case_id,
                    row.get("referenced_type"),
                    row["referenced_id"],
                    row["index_identifier"]
                )
                case_ids_by_domain[domain].append(case_id)

        self.stdout.write('domain,case_id,referenced_id,index_identifier,form_id,status')
        for domain, case_ids in case_ids_by_domain.items():
            logger.info(f"Processing {len(case_ids)} for domain '{domain}'")
            case_blocks_and_meta = []
            cases = CaseAccessors(domain).get_cases(case_ids)
            for case in cases:
                meta = case_metas[case.case_id]
                index = get_index_by_ref_id(case, meta)
                if not index:
                    self.write_output(meta, '', 'index not found')
                else:
                    case_blocks_and_meta.append((
                        meta,
                        CaseBlock(
                            case.case_id, index={
                                meta.index_identifier: (index.referenced_type, '', index.relationship)
                            }
                        ).as_text()
                    ))

                if self.check_submit_case_blocks(domain, case_blocks_and_meta, batch_size=100):
                    case_blocks_and_meta = []

            # submit any remaining changes
            self.check_submit_case_blocks(domain, case_blocks_and_meta, batch_size=0)

    def check_submit_case_blocks(self, domain, case_block_and_meta, batch_size=100):
        if len(case_block_and_meta) < batch_size:
            return False

        logger.info(f"\tUpdating {len(case_block_and_meta)} for domain '{domain}'")

        metas = [cm[0] for cm in case_block_and_meta]
        case_blocks = [cm[1] for cm in case_block_and_meta]
        form_id = 'dry_run'
        if not self.dry_run:
            form, _ = submit_case_blocks(case_blocks, domain, username=self.username)
            form_id = form.form_id

        for meta in metas:
            self.write_output(meta, form_id, 'removed')

        return True

    def write_output(self, meta, form_id, status):
        self.stdout.write(
            f'{meta.domain},{meta.case_id},{meta.referenced_id},{meta.index_identifier},{form_id},{status}'
        )


def get_index_by_ref_id(case, case_meta: CaseMeta):
    found = [
        index for index in case.indices
        if (
            index.referenced_id == case_meta.referenced_id
            and index.identifier == case_meta.index_identifier
            and (not case_meta.referenced_type or case_meta.referenced_type == index.referenced_type)
        )
    ]
    return found[0] if found else None
