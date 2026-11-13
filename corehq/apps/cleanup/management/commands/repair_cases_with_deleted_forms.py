import csv
import json
import os

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.cleanup.deleted_forms import ScanPosition, iter_scan_pages


class Command(BaseCommand):
    help = """Repair cases with transactions for deleted forms.

    A form deleted without first being archived leaves case transactions
    that still apply its updates while it is soft deleted, and make
    rebuilding the case fail with XFormNotFound once it is hard deleted.

    scan: read-only. Appends affected cases to a CSV. Resumable.
    """

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(required=True, dest='sub_command')

        scan = subparsers.add_parser(
            'scan', help='Find affected cases. Does not change anything.'
        )
        scan.set_defaults(func=self.scan)
        scan.add_argument('domain')
        scan.add_argument(
            'cases_csv',
            help='Affected cases are appended here. A checkpoint is kept '
            'next to it so a rerun resumes the scan.',
        )
        scan.add_argument(
            '--max-cases',
            type=int,
            help='Stop after scanning about this many cases. Rerun to continue.',
        )
        scan.add_argument('--include-deleted', action='store_true')
        scan.add_argument('--page-size', type=int, default=1000)

    def handle(self, func, **options):
        func(**options)

    def scan(
        self, domain, cases_csv, max_cases, include_deleted, page_size, **kw
    ):
        checkpoint = Checkpoint(f'{cases_csv}.checkpoint')
        position = checkpoint.load(domain, include_deleted)
        # tie the CSV to these arguments even if no pages are found
        checkpoint.save(domain, include_deleted, position or ScanPosition())
        scanned = found = 0
        with open(cases_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            pages = iter_scan_pages(
                domain, position, include_deleted, page_size
            )
            for page in pages:
                for case_id, form_ids in page.deleted_form_ids_by_case.items():
                    writer.writerow([case_id, ' '.join(sorted(form_ids))])
                f.flush()
                checkpoint.save(domain, include_deleted, page.position)
                scanned += page.case_count
                found += len(page.deleted_form_ids_by_case)
                self.stdout.write(f'Scanned {scanned} cases, found {found}')
                if max_cases and scanned >= max_cases:
                    self.stdout.write(
                        'Reached --max-cases. Rerun to continue the scan.'
                    )
                    return
        self.stdout.write(
            f'Scan complete. This run scanned {scanned} cases '
            f'and found {found}. All affected cases are in {cases_csv}'
        )


class Checkpoint:
    """Scan position saved as JSON, tied to the scan's arguments"""

    def __init__(self, path):
        self.path = path

    def load(self, domain, include_deleted):
        if not os.path.exists(self.path):
            return None
        with open(self.path) as f:
            data = json.load(f)
        if (data['domain'], data['include_deleted']) != (
            domain,
            include_deleted,
        ):
            raise CommandError(
                f'{self.path} is for a scan of domain {data["domain"]!r} '
                f'with include_deleted={data["include_deleted"]}. Use a '
                'different CSV, or delete the CSV and checkpoint to start over.'
            )
        return ScanPosition(
            done_db_aliases=tuple(data['done_db_aliases']),
            db_alias=data['db_alias'],
            last_pk=data['last_pk'],
        )

    def save(self, domain, include_deleted, position):
        with open(self.path, 'w') as f:
            json.dump(
                {
                    'domain': domain,
                    'include_deleted': include_deleted,
                    'done_db_aliases': list(position.done_db_aliases),
                    'db_alias': position.db_alias,
                    'last_pk': position.last_pk,
                },
                f,
            )
