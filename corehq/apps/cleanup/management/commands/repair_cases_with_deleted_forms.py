import csv
import json
import os
import time
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.cleanup.deleted_forms import (
    ScanPosition,
    iter_scan_pages,
    repair_case,
)


class Command(BaseCommand):
    help = """Repair cases with transactions for deleted forms.

    A form deleted without first being archived leaves case transactions
    that still apply its updates while it is soft deleted, and make
    rebuilding the case fail with XFormNotFound once it is hard deleted.

    scan: read-only. Appends affected cases to a CSV. Resumable.
    fix: revokes those transactions and rebuilds the cases listed in the
    CSV, at a limited rate. Resumable.
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

        fix = subparsers.add_parser(
            'fix', help='Revoke transactions and rebuild cases from a scan.'
        )
        fix.set_defaults(func=self.fix)
        fix.add_argument('domain')
        fix.add_argument('cases_csv', help='Output of scan')
        fix.add_argument(
            'done_csv',
            help='Results are appended here, and cases already in it are '
            'skipped. Create <done_csv>.stop to stop after the current case.',
        )
        fix.add_argument(
            '--max-cases',
            type=int,
            required=True,
            help='Repair at most this many cases in this run',
        )
        fix.add_argument(
            '--per-minute',
            type=float,
            default=30,
            help='Repair at most this many cases per minute (default 30)',
        )

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

    def fix(self, domain, cases_csv, done_csv, max_cases, per_minute, **kw):
        if Checkpoint(f'{cases_csv}.checkpoint').domain() != domain:
            raise CommandError(
                f'{cases_csv} is not the output of a scan of domain {domain!r}'
            )
        done = {row[0] for row in read_csv(done_csv)}
        # a dict drops cases repeated by a scan resumed from its checkpoint
        cases = {
            case_id: form_ids.split()
            for case_id, form_ids in read_csv(cases_csv)
        }
        todo = [
            (case_id, form_ids)
            for case_id, form_ids in cases.items()
            if case_id not in done
        ][:max_cases]
        self.stdout.write(
            f'{len(done)} cases already done, {len(todo)} to repair now'
        )

        stop_file = f'{done_csv}.stop'
        interval = 60 / per_minute
        counts = Counter()
        with open(done_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            for i, (case_id, form_ids) in enumerate(todo, start=1):
                if os.path.exists(stop_file):
                    self.stdout.write(f'Found {stop_file}, stopping')
                    break
                started = time.monotonic()
                status = self._repair(domain, case_id, form_ids)
                writer.writerow([case_id, status])
                f.flush()
                counts[status.split(':')[0]] += 1
                if i % 100 == 0:
                    self.stdout.write(f'{i}/{len(todo)} {dict(counts)}')
                time.sleep(max(0, interval - (time.monotonic() - started)))
        self.stdout.write(f'Done: {dict(counts)}. Results are in {done_csv}')

    def _repair(self, domain, case_id, form_ids):
        try:
            revoked = repair_case(domain, case_id, form_ids)
        except Exception as e:
            return f'error: {e!r}'
        return f'revoked: {revoked}' if revoked else 'nothing to repair'


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='') as f:
        return list(csv.reader(f))


class Checkpoint:
    """Scan position saved as JSON, tied to the scan's arguments"""

    def __init__(self, path):
        self.path = path

    def load(self, domain, include_deleted):
        data = self._read()
        if data is None:
            return None
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

    def domain(self):
        data = self._read()
        return data['domain'] if data else None

    def _read(self):
        if not os.path.exists(self.path):
            return None
        with open(self.path) as f:
            return json.load(f)

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
