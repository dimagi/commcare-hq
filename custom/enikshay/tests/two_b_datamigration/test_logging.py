from __future__ import absolute_import
import csv
import datetime
import os
from contextlib import contextmanager

from django.core.management import call_command
from django.test import SimpleTestCase
from mock import patch, MagicMock
from openpyxl import Workbook

from corehq.apps.users.models import CommCareUser
from corehq.apps.users.models import DeviceIdLastUsed
from corehq.util.workbook_reading.adapters.xlsx import _XLSXWorkbookAdaptor
from custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases import (
    Command as ImportDRTBCasesCommand,
    DRUG_MAP,
)
from custom.enikshay.two_b_datamigration.management.commands.drtb_import_history import (
    Command as DRTBImportHistoryCommand
)

IMPORT_ROWS = [
    # A minimal valid row
    ["1", None, None, None, "XX-XXX-0-X-00-00001", None, None, datetime.date(2017, 1, 1), "John Doe", None,
     50, "123 fake st", "91-123-456-7890"] + ([None] * 9) + ["some district", None, None, "some phi"],
    # A row that's missing person_name (a required field)
    ["2", None, None, None, "XX-XXX-0-X-00-00002", None, None, datetime.date(2017, 1, 1), None, None, 50,
     "123 fake st", "91-123-456-7890"] + ([None] * 9) + ["some district", None, None, "some phi"],
]


class ImportDRTBTestMixin(object):

    domain = "fake-domain"

    @contextmanager
    def drtb_import(self, import_rows, format, commit=False):
        """
        Return a context manager that yields the file handle and rows of the csv log file created by running the
        drtb case import on the given import_rows. format is the format parameter passed to import_drtb_cases.
        """

        match_phi_path = "custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases.match_phi"
        match_location_path = \
            "custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases.match_location"
        open_any_workbook_path = \
            "custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases.open_any_workbook"
        get_users_path = \
            "custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases.get_users_by_location_id"
        mock_user = MagicMock(
            domain=self.domain,
            devices=[DeviceIdLastUsed(device_id="drtb-case-import-script")],
            is_demo_user=False,
            user_data={"id_issuer_body": "FOO"},
            spec=CommCareUser,
        )

        with patch(match_location_path, return_value=(None, None)),\
                patch(match_phi_path, return_value=(None, None)),\
                patch(get_users_path, return_value=[mock_user]), \
                patch(open_any_workbook_path) as open_any_workbook_mock:
            rows = [[]] + [[]] + import_rows  # Add headers to the row list
            open_any_workbook_mock.return_value.__enter__.return_value = self._create_workbook(rows)
            with patch.object(ImportDRTBCasesCommand, 'generate_id', return_value="foo"):
                try:

                    extra_args = []
                    if commit:
                        extra_args.append("--commit")
                    call_command(
                        'import_drtb_cases',
                        self.domain,
                        "fake-excel-file-path.xlsx",
                        format,
                        *extra_args
                    )

                    with open("drtb-import-foo.csv", "r") as log_csv:
                        reader = csv.DictReader(log_csv)
                        lines = [line for line in reader]
                        log_csv.seek(0)
                        yield log_csv, lines
                finally:
                    os.remove("drtb-import-foo.csv")

    def _create_workbook(self, rows):
        """
        Return a workbook consisting of the given rows like that returned by opening an excel
        file with open_any_workbook()
        """
        workbook = Workbook()
        worksheet = workbook.active
        for row in rows:
            worksheet.append(row)
        wrapped_workbook = _XLSXWorkbookAdaptor(workbook).to_workbook()
        return wrapped_workbook


class TestLogCreation(SimpleTestCase, ImportDRTBTestMixin):

    def test_simple_import(self):
        with self.drtb_import(IMPORT_ROWS, "mumbai") as (_, result_rows):

            # Confirm that the valid row in our input sheet results in all case_ids being logged
            self.assertEqual(
                len(result_rows[0].get("case_ids", "").split(",")),
                # A person, occurrence, episode, and two secondary_owner cases, plus one drug_resistance case for
                # each drug
                5 + len(DRUG_MAP)
            )
            self.assertIsNone(result_rows[0]['exception'])

            # Confirm that the invalid row in our input sheet results in an exception being logged.
            self.assertFalse(result_rows[1]['case_ids'])
            self.assertIsNotNone(result_rows[1]['exception'])


class TestDRTBImportHistoryCommand(SimpleTestCase, ImportDRTBTestMixin):

    def test_get_row(self):

        with self.drtb_import(IMPORT_ROWS, "mumbai") as (csv_file, csv_rows):
            output = DRTBImportHistoryCommand.handle_get_row("some bad id", csv_file)
            csv_file.seek(0)
            self.assertEqual(output, "case not found\n")

            row_case_ids = csv_rows[0]['case_ids'].split(",")
            for case_id in row_case_ids:
                output = DRTBImportHistoryCommand.handle_get_row(case_id, csv_file)
                csv_file.seek(0)
                self.assertEqual(output, "row: 2\n")

    def test_get_outcome(self):
        with self.drtb_import(IMPORT_ROWS, "mumbai") as (csv_file, csv_rows):
            output = DRTBImportHistoryCommand.handle_get_outcome("2", csv_file)
            csv_file.seek(0)

            # Confirm that the outcome contains all the expected case ids
            self.assertNotIn("Traceback", output, "Expected list of case ids, but output was: {}".format(output))
            self.assertEqual(
                len(output.split()),
                5 + len(DRUG_MAP)
            )

            output = DRTBImportHistoryCommand.handle_get_outcome("3", csv_file)
            csv_file.seek(0)

            # Confirm that the outcome contains the exception raised for the row
            self.assertTrue("person_name is required" in output)
