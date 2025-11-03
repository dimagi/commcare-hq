from django.test import TestCase

import pytest

from corehq.apps.case_importer import exceptions
from corehq.apps.data_dictionary.models import (
    CaseProperty,
    CasePropertyAllowedValue,
    CaseType,
)


class TestCasePropertyValidation:

    def test_valid_date(self):
        valid_date = '2025-11-02'
        # check_validity raises exception on invalid date so just
        # calling it and not getting an exception indicates validity
        prop = CaseProperty(data_type=CaseProperty.DataType.DATE)
        prop.check_validity(valid_date)

    @pytest.mark.parametrize('value', [
        "2022",
        "2022-14-03",
        "Embedded 2025-11-02 in a longer string",
        "  2025-11-02 ",  # caller is responsible for stripping any surrounding whitespace
    ])
    def test_check_invalid_date(self, value):
        prop = CaseProperty(data_type=CaseProperty.DataType.DATE)
        with pytest.raises(exceptions.InvalidDate):
            prop.check_validity(value)

    def test_unvalidated_type(self):
        # Barcodes are not validated
        prop = CaseProperty(data_type=CaseProperty.DataType.BARCODE)
        prop.check_validity('123')

    @pytest.mark.parametrize('value', ['42', '-10', '3.14', '-3.14'])
    def test_check_valid_number(self, value):
        prop = CaseProperty(data_type=CaseProperty.DataType.NUMBER)
        prop.check_validity(value)

    @pytest.mark.parametrize('value', ['not a number', '12.34.56'])
    def test_check_invalid_number(self, value):
        prop = CaseProperty(data_type=CaseProperty.DataType.NUMBER)
        with pytest.raises(exceptions.InvalidNumber):
            prop.check_validity(value)

    @pytest.mark.parametrize('value', [
        '42.123 -71.456',
        '42.123 -71.456 100',
        '42.123 -71.456 100 5',
        '-42.123 -71.456 -10 5.5',  # Negative altitude, decimal precision
        '42123 -71456',  # Note: Validation does not check degrees
    ])
    def test_check_valid_gps(self, value):
        prop = CaseProperty(data_type=CaseProperty.DataType.GPS)
        prop.check_validity(value)

    @pytest.mark.parametrize('value', [
        '42.123 +71.456',  # plus sign
        '42.123',  # Missing longitude
        "66° 34' N 23° 27.5' E",
        'The North Pole',
    ])
    def test_check_invalid_gps(self, value):
        prop = CaseProperty(data_type=CaseProperty.DataType.GPS)
        with pytest.raises(exceptions.InvalidGPS):
            prop.check_validity(value)

    @pytest.mark.parametrize('value', [
        '(555) 123-4567',
        '+1 555-123-4567',
        '081 234 5678',
        '12.34.56.78.90',
        '12345',  # Minimum 5 digits
        '(123) 45',  # Exactly 5 digits with formatting
    ])
    def test_check_valid_phone_number(self, value):
        prop = CaseProperty(data_type=CaseProperty.DataType.PHONE_NUMBER)
        prop.check_validity(value)

    @pytest.mark.parametrize('value', [
        '(555) 123-4567 ext 89',  # Invalid characters
        '*#12345',  # Invalid characters
        '1234',  # Only 4 digits - too few
        '(12) 34',  # Only 4 digits with formatting
        '+-+-+-',  # No digits
    ])
    def test_check_invalid_phone_number(self, value):
        prop = CaseProperty(data_type=CaseProperty.DataType.PHONE_NUMBER)
        with pytest.raises(exceptions.InvalidPhoneNumber):
            prop.check_validity(value)


class TestCasePropertyValidationWithDB(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        domain = 'test-case-property'
        case_type = CaseType.objects.create(domain=domain, name="case_type")
        cls.addClassCleanup(case_type.delete)
        cls.prop = CaseProperty.objects.create(
            name='prop',
            case_type=case_type,
            data_type=CaseProperty.DataType.SELECT
        )
        cls.valid_choices = ('foo', 'bar', 'baz')
        for choice in cls.valid_choices:
            CasePropertyAllowedValue.objects.create(
                case_property=cls.prop,
                allowed_value=choice,
            )

    def test_check_valid_selections(self):
        for choice in self.valid_choices:
            self.prop.check_validity(choice)

    def test_check_invalid_choice(self):
        # We require strict matching, including case. Uppercase a valid choice
        # and ensure it is not accepted.
        with pytest.raises(exceptions.InvalidSelectValue):
            self.prop.check_validity('FOO')
