import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from corehq.apps.cleanup.tests.test_deleted_forms import (
    DOMAIN,
    create_case_with_update,
    delete_all_cases_and_forms,
    hard_delete,
)
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import sharded

COMMAND = 'repair_cases_with_deleted_forms'


@sharded
class TestScan(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cases_csv = Path(tmp.name) / 'cases.csv'

    def tearDown(self):
        delete_all_cases_and_forms()
        super().tearDown()

    def test_writes_affected_cases(self):
        expected = [self.broken_case() for _ in range(2)]
        create_case_with_update()  # healthy

        call_command(COMMAND, 'scan', DOMAIN, self.cases_csv)

        assert sorted(self.rows()) == sorted(expected)

    def test_resumes_after_max_cases(self):
        expected = [self.broken_case() for _ in range(3)]
        scan = [COMMAND, 'scan', DOMAIN, self.cases_csv, '--page-size', '1']

        call_command(*scan, '--max-cases', '1')
        assert len(self.rows()) == 1
        call_command(*scan)
        assert sorted(self.rows()) == sorted(expected)
        call_command(*scan)  # complete: nothing new
        assert len(self.rows()) == 3

    def test_checkpoint_for_other_arguments_is_rejected(self):
        call_command(COMMAND, 'scan', DOMAIN, self.cases_csv)
        with self.assertRaisesRegex(CommandError, 'include_deleted=False'):
            call_command(
                COMMAND, 'scan', DOMAIN, self.cases_csv, '--include-deleted'
            )
        with self.assertRaisesRegex(CommandError, DOMAIN):
            call_command(COMMAND, 'scan', 'other-domain', self.cases_csv)

    def broken_case(self):
        case_id, _, form_id = create_case_with_update()
        hard_delete(form_id)
        return [case_id, form_id]

    def rows(self):
        with open(self.cases_csv) as f:
            return list(csv.reader(f))


@sharded
class TestFix(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cases_csv = Path(tmp.name) / 'cases.csv'
        self.done_csv = Path(tmp.name) / 'done.csv'

    def tearDown(self):
        delete_all_cases_and_forms()
        super().tearDown()

    def test_repairs_cases(self):
        case_ids = self.scan_broken_cases(2)
        self.fix('--max-cases', '10')
        assert sorted(self.done()) == sorted(
            [case_id, 'revoked: 1'] for case_id in case_ids
        )
        for case_id in case_ids:
            case = CommCareCase.objects.get_case(case_id, DOMAIN)
            assert case.get_case_property('prop') == 'created'

    def test_resumes_after_max_cases(self):
        case_ids = self.scan_broken_cases(3)
        self.fix('--max-cases', '2')
        assert len(self.done()) == 2
        self.fix('--max-cases', '2')
        assert sorted(row[0] for row in self.done()) == sorted(case_ids)

    def test_case_listed_twice_is_repaired_once(self):
        [case_id] = self.scan_broken_cases(1)
        with open(self.cases_csv) as f:
            row = f.read()
        with open(self.cases_csv, 'a') as f:
            f.write(row)
        self.fix('--max-cases', '10')
        assert self.done() == [[case_id, 'revoked: 1']]

    def test_cases_from_scan_of_other_domain_are_rejected(self):
        self.scan_broken_cases(1)
        with self.assertRaisesRegex(CommandError, 'other-domain'):
            call_command(
                COMMAND,
                'fix',
                'other-domain',
                self.cases_csv,
                self.done_csv,
                '--max-cases',
                '10',
            )
        assert not self.done_csv.exists()

    def test_cases_not_from_a_scan_are_rejected(self):
        self.scan_broken_cases(1)
        Path(f'{self.cases_csv}.checkpoint').unlink()
        with self.assertRaisesRegex(CommandError, 'not the output of a scan'):
            self.fix('--max-cases', '10')
        assert not self.done_csv.exists()

    def test_stop_file(self):
        self.scan_broken_cases(1)
        Path(f'{self.done_csv}.stop').touch()
        self.fix('--max-cases', '10')
        assert self.done() == []

    def test_error_is_recorded_and_run_continues(self):
        case_ids = self.scan_broken_cases(2)
        with patch(
            'corehq.apps.cleanup.management.commands'
            '.repair_cases_with_deleted_forms.repair_case',
            side_effect=[ValueError('boom'), 1],
        ):
            self.fix('--max-cases', '10')
        statuses = [status for _, status in self.done()]
        assert statuses == ["error: ValueError('boom')", 'revoked: 1']
        assert sorted(row[0] for row in self.done()) == sorted(case_ids)

    def scan_broken_cases(self, count):
        case_ids = []
        for _ in range(count):
            case_id, _, form_id = create_case_with_update()
            hard_delete(form_id)
            case_ids.append(case_id)
        call_command(COMMAND, 'scan', DOMAIN, self.cases_csv)
        return case_ids

    def fix(self, *args):
        call_command(
            COMMAND,
            'fix',
            DOMAIN,
            self.cases_csv,
            self.done_csv,
            '--per-minute',
            '60000',
            *args,
        )

    def done(self):
        with open(self.done_csv) as f:
            return list(csv.reader(f))
