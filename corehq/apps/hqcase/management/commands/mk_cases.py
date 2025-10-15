from typing import Generator

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks

CASE_BLOCK_COUNT = 1000


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('num_cases', type=int)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, domain, num_cases, *args, **options):
        submitter = get_case_block_submitter(domain, options['dry_run'])
        next(submitter)
        for _ in range(num_cases):
            case_block = CaseBlock(
                # TODO: ...
            )
            submitter.send(case_block)
        submitter.close()


def get_case_block_submitter(
    domain: str,
    dry_run: bool,
) -> Generator[None, CaseBlock, None]:
    """
    Returns a generator coroutine that is sent case blocks and submits
    them in chunks of CASE_BLOCK_COUNT.
    """
    case_blocks = []
    try:
        while True:
            case_block = yield
            case_blocks.append(case_block.as_text())
            if len(case_blocks) >= CASE_BLOCK_COUNT:
                chunk = case_blocks[:CASE_BLOCK_COUNT]
                case_blocks = case_blocks[CASE_BLOCK_COUNT:]
                if not dry_run:
                    submit_case_blocks(chunk, domain, device_id=__name__)
    except GeneratorExit:
        if case_blocks:
            if not dry_run:
                submit_case_blocks(case_blocks, domain, device_id=__name__)
