import datetime
from decimal import Decimal

import pytest
from openpyxl.styles import numbers
from testil import eq

from couchexport.util import get_excel_format_value

from corehq.apps.export.const import EMPTY_VALUE, MISSING_VALUE


def check(input, output, format, output_type):
    excel_format, value = get_excel_format_value(input)
    eq(excel_format, format)
    eq(value, output)
    eq(type(value), output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('3423', 3423, numbers.FORMAT_NUMBER, int),
    ('-234', -234, numbers.FORMAT_NUMBER, int),
    (324, 324, numbers.FORMAT_NUMBER, int),
])
def test_integers(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('4.0345', 4.0345, numbers.FORMAT_NUMBER_00, float),
    ('-3.234', -3.234, numbers.FORMAT_NUMBER_00, float),
    (5.032, 5.032, numbers.FORMAT_NUMBER_00, float),
    (Decimal('3.00'), 3.00, numbers.FORMAT_NUMBER_00, float),
])
def test_decimal(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('TRUE', True, numbers.FORMAT_GENERAL, bool),
    ('True', True, numbers.FORMAT_GENERAL, bool),
    ('true', True, numbers.FORMAT_GENERAL, bool),
    (True, True, numbers.FORMAT_GENERAL, bool),

    ('FALSE', False, numbers.FORMAT_GENERAL, bool),
    ('False', False, numbers.FORMAT_GENERAL, bool),
    ('false', False, numbers.FORMAT_GENERAL, bool),
    (False, False, numbers.FORMAT_GENERAL, bool),
])
def test_boolean(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('6,9234', 6.9234, numbers.FORMAT_NUMBER_00, float),
    ('-5,342', -5.342, numbers.FORMAT_NUMBER_00, float),
])
def test_decimal_eur(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('80%', 0.8, numbers.FORMAT_PERCENTAGE, float),
    ('-50%', -0.5, numbers.FORMAT_PERCENTAGE, float),
    ('3.45%', 0.0345, numbers.FORMAT_PERCENTAGE_00, float),
    ('-4.35%', -0.0435, numbers.FORMAT_PERCENTAGE_00, float),
])
def test_percentage(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('3,000.0234', 3000.0234, numbers.FORMAT_NUMBER_COMMA_SEPARATED1, float),
    ('3,234,000.342', 3234000.342, numbers.FORMAT_NUMBER_COMMA_SEPARATED1, float),
    ('5,000,343', 5000343, numbers.FORMAT_NUMBER_COMMA_SEPARATED1, float),
    ('-5,334.32', -5334.32, numbers.FORMAT_NUMBER_COMMA_SEPARATED1, float),
])
def test_comma_separated_us(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('5.600,0322', 5600.0322, numbers.FORMAT_NUMBER_COMMA_SEPARATED2, float),
    ('5.600,0322', 5600.0322, numbers.FORMAT_NUMBER_COMMA_SEPARATED2, float),
    ('8.435.600,0322', 8435600.0322, numbers.FORMAT_NUMBER_COMMA_SEPARATED2, float),
    ('5.555.600', 5555600, numbers.FORMAT_NUMBER_COMMA_SEPARATED2, float),
    ('-2.433,032', -2433.032, numbers.FORMAT_NUMBER_COMMA_SEPARATED2, float),
])
def test_comma_separated_eur(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('$3,534.02', 3534.02, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('$99', 99, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('$5,000', 5000, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('-$234.02', -234.02, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('$4.4302', 4.4302, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
])
def test_currency_usd(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('$3,534.02', 3534.02, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('$99', 99, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('$5,000', 5000, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('-$234.02', -234.02, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
    ('$4.4302', 4.4302, numbers.FORMAT_CURRENCY_USD_SIMPLE, float),
])
def test_currency_eur(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('2020-01-20', datetime.datetime(2020, 1, 20, 0, 0),
        numbers.FORMAT_DATE_YYYYMMDD2, datetime.datetime),
    ('2020/01/20', datetime.datetime(2020, 1, 20, 0, 0),
        numbers.FORMAT_DATE_YYYYMMDD2, datetime.datetime),
    ('2020.01.20', datetime.datetime(2020, 1, 20, 0, 0),
        numbers.FORMAT_DATE_YYYYMMDD2, datetime.datetime),
    (datetime.date(2020, 1, 20), datetime.date(2020, 1, 20),
        numbers.FORMAT_DATE_YYYYMMDD2, datetime.date),
])
def test_date(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('2020-01-20 12:33',
        datetime.datetime(2020, 1, 20, 12, 33),
        numbers.FORMAT_DATE_DATETIME, datetime.datetime),
    ('2020-01-20 12:33:22',
        datetime.datetime(2020, 1, 20, 12, 33, 22),
        numbers.FORMAT_DATE_DATETIME, datetime.datetime),
    ('2020-01-20 1:33:22PM',
        datetime.datetime(2020, 1, 20, 13, 33, 22),
        numbers.FORMAT_DATE_DATETIME, datetime.datetime),
    ('2020-01-20 09:33:22.890000-6:00',
        datetime.datetime(2020, 1, 20, 9, 33, 22, 890000),
        numbers.FORMAT_DATE_DATETIME, datetime.datetime),
    ('2020-01-20 09:33:22.890000-6',
        datetime.datetime(2020, 1, 20, 9, 33, 22, 890000),
        numbers.FORMAT_DATE_DATETIME, datetime.datetime),
    (datetime.datetime(2020, 1, 20, 11, 11),
        datetime.datetime(2020, 1, 20, 11, 11),
        numbers.FORMAT_DATE_DATETIME, datetime.datetime),
    ('2020-01-17T15:45:37.268000Z',
        datetime.datetime(2020, 1, 17, 15, 45, 37, 268000),
        numbers.FORMAT_DATE_DATETIME, datetime.datetime),
])
def test_datetime(input, output, format, output_type):
    check(input, output, format, output_type)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('12:33', '12:33', numbers.FORMAT_DATE_TIME4, str),
    ('12:33:66', '12:33:66', numbers.FORMAT_DATE_TIME4, str),
    ('09:33:22.890000-6:00', '09:33:22.890000-6:00', numbers.FORMAT_DATE_TIME4, str),
    ('09:33:22.890000-6', '09:33:22.890000-6', numbers.FORMAT_DATE_TIME4, str),
])
def test_time(input, output, format, output_type):
    check(input, output, format, output_type)


def test_missing():
    check(MISSING_VALUE, MISSING_VALUE, numbers.FORMAT_TEXT, str)


def test_empty():
    check(EMPTY_VALUE, EMPTY_VALUE, numbers.FORMAT_TEXT, str)


@pytest.mark.parametrize("input, output, format, output_type", [
    ('hi this is text', 'hi this is text', numbers.FORMAT_TEXT, str),
    ('1241234eeeesffsfs', '1241234eeeesffsfs', numbers.FORMAT_TEXT, str),
    ({'en': 'Thanks', 'de': 'Danke'}, "{'en': 'Thanks', 'de': 'Danke'}", numbers.FORMAT_TEXT, str),
])
def test_text(input, output, format, output_type):
    check(input, output, format, output_type)


def test_bad_date_string():
    check('112020-02-2609', '112020-02-2609', numbers.FORMAT_TEXT, str)
