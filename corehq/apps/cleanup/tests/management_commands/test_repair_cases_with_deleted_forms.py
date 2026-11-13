import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import CommandError, call_command
from django.test import TestCase

from corehq.apps.cleanup.tests.test_deleted_forms import (
    DOMAIN,
    create_case_with_update,
    delete_all_cases_and_forms,
    hard_delete,
)
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
