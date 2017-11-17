from __future__ import absolute_import
from django.test import SimpleTestCase
from openpyxl import Workbook

from corehq.util.workbook_reading.adapters.xlsx import _XLSXWorkbookAdaptor
from custom.enikshay.two_b_datamigration.management.commands.import_drtb_cases import (
    ColumnMapping,
    clean_phone_number,
    clean_contact_phone_number)


class MockColumnMapping(ColumnMapping):
    mapping_dict = {
        "col0": 0,
        "col1": 1,
        "col2": 2,
    }
    required_fields = [
        "col1",
    ]


class TestMappings(SimpleTestCase):

    def test_missing_key(self):
        # Confirm that fetching a column that does not exist for this mapping (but does exist in another mapping)
        # returns None.
        row = self.get_row([])
        value = MockColumnMapping.get_value("person_name", row)
        self.assertIsNone(value)

    def test_non_existent_key(self):
        # Confirm that fetching a column that does not exist for this mapping (or any other)
        # raises an exception.
        row = self.get_row([])
        with self.assertRaises(KeyError):
            MockColumnMapping.get_value("pesron_name", row)  # Note the typo in the column id

    def test_existing_key(self):
        # Confirm that fetching a column that does exist returns the right value
        row = self.get_row(["foo", "bar"])
        value = MockColumnMapping.get_value("col1", row)
        self.assertEqual(value, "bar")

    def test_empty_value_in_row(self):

        row = self.get_row([None, "1"])
        value = MockColumnMapping.get_value("col0", row)
        self.assertEqual(value, None)

        # Index out of range on the row
        value = MockColumnMapping.get_value("col2", row)
        self.assertEqual(value, None)

    def test_required_value_missing(self):
        row = self.get_row(["0", None, "2"])
        # col1 is required
        with self.assertRaises(Exception) as cm:
            MockColumnMapping.check_for_required_fields(row)
        self.assertEqual(cm.exception.message, "col1 is required")

    def test_required_value_present(self):
        row = self.get_row(["0", "1"])
        # col1 is required
        MockColumnMapping.check_for_required_fields(row)

    def get_row(self, values):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(values)

        wrapped_workbook = _XLSXWorkbookAdaptor(workbook).to_workbook()
        wrapped_worksheet = wrapped_workbook.worksheets[0]
        return list(wrapped_worksheet.iter_rows())[0]


class TestCleaningFunctions(SimpleTestCase):

    def test_clean_phone_number(self):
        good_number = "911234567890"
        good_number_with_punc = "+91 123-456-7890"
        good_short_number = "123-456-7890"

        for number in (good_number, good_number_with_punc, good_short_number):
            clean_number = clean_phone_number(number)
            clean_12_number = clean_contact_phone_number(clean_number)
            self.assertEqual(clean_12_number, "911234567890")
            self.assertEqual(clean_number, "1234567890")

        # Confirm that clean_contact_phone_number returns none for badly formatted numbers
        self.assertIsNone(clean_contact_phone_number("123"))
        # Confirm that clean_phone_number returns the number for badly formatted numbers
        self.assertEqual(clean_phone_number("123"), "123")
