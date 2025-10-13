import datetime

from django.test import TestCase

import pytest

from corehq.apps.case_importer import exceptions
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CaseType,
)


class TestCaseProperty(TestCase):
    domain_name = 'test-case-property'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_type = CaseType(name="caseType", domain=cls.domain_name)
        cls.case_type.save()
        cls.date_property = CaseProperty(
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.DATE,
            name="dob",
        )
        cls.date_property.save()
        cls.valid_date = datetime.date.today().isoformat()
        cls.select_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.SELECT,
            name="status",
        )
        cls.valid_choices = ["todo", "in-progress", "complete"]
        for choice in cls.valid_choices:
            CasePropertyAllowedValue.objects.create(
                case_property=cls.select_property,
                allowed_value=choice
            )
        cls.barcode_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.BARCODE,
            name="patient_code",
        )
        cls.number_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.NUMBER,
            name="height_m",
        )
        cls.gps_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.GPS,
            name="location",
        )
        cls.phone_number_property = CaseProperty.objects.create(
            case_type=cls.case_type,
            data_type=CaseProperty.DataType.PHONE_NUMBER,
            name="contact",
        )

    def test_check_valid_date(self):
        # check_validity raises exception on invalid date so just
        # calling it and not getting an exception indicates validity
        self.date_property.check_validity(self.valid_date)

    def test_check_invalid_date(self):
        with pytest.raises(exceptions.InvalidDate):
            self.date_property.check_validity("2022")
        with pytest.raises(exceptions.InvalidDate):
            self.date_property.check_validity("2022-14-03")
        with pytest.raises(exceptions.InvalidDate):
            self.date_property.check_validity(f"Embedded {self.valid_date} in a longer string")
        with pytest.raises(exceptions.InvalidDate):
            # caller is responsible for stripping any surrounding whitespace
            self.date_property.check_validity(f"  {self.valid_date} ")

    def test_check_valid_selections(self):
        # Simply not raising an exception indicates it passes validity check
        for choice in self.valid_choices:
            self.select_property.check_validity(choice)

    def test_check_invalid_choice(self):
        # We require strict matching, including case. Uppercase a valid choice
        # and ensure it is not accepted.
        with pytest.raises(exceptions.InvalidSelectValue):
            self.select_property.check_validity(self.valid_choices[0].upper())

    def test_unvalidated_type(self):
        # Barcodes are not validated
        self.barcode_property.check_validity('123')

    def test_check_valid_number(self):
        # Simply not raising an exception indicates it passes validity check
        self.number_property.check_validity('42')
        self.number_property.check_validity('3.14')
        self.number_property.check_validity('-10')
        self.number_property.check_validity('-3.14')

    def test_check_invalid_number(self):
        with pytest.raises(exceptions.InvalidNumber):
            self.number_property.check_validity('not a number')
        with pytest.raises(exceptions.InvalidNumber):
            self.number_property.check_validity('12.34.56')

    def test_check_valid_gps(self):
        valid_values = [
            '42.123 -71.456',
            '42.123 -71.456 100',
            '42.123 -71.456 100 5',
            '-42.123 -71.456 -10 5.5',  # Negative altitude, decimal precision
            '42123 -71456',  # Note: Validation does not check degrees
        ]
        for value in valid_values:
            self.gps_property.check_validity(value)

    def test_check_invalid_gps(self):
        invalid_values = [
            '42.123 +71.456',  # plus sign
            '42.123',  # Missing longitude
            "66° 34' N 23° 27.5' E",
            'The North Pole',
        ]
        for value in invalid_values:
            with pytest.raises(exceptions.InvalidGPS):
                self.gps_property.check_validity(value)

    def test_check_valid_phone_number(self):
        valid_values = [
            '(555) 123-4567',
            '+1 555-123-4567',
            '081 234 5678',
            '12.34.56.78.90',
        ]
        for value in valid_values:
            self.phone_number_property.check_validity(value)

    def test_check_invalid_phone_number(self):
        invalid_values = [
            '(555) 123-4567 ext 89',
            '*#12345',
        ]
        for value in invalid_values:
            with pytest.raises(exceptions.InvalidPhoneNumber):
                self.phone_number_property.check_validity(value)
