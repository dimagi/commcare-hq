import datetime
import re
from decimal import Decimal

import dateutil
from openpyxl.styles import numbers

from corehq.apps.export.const import MISSING_VALUE, EMPTY_VALUE

_dirty_chars = re.compile(
    '[\x00-\x08\x0b-\x1f\x7f-\x84\x86-\x9f\ud800-\udfff\ufdd0-\ufddf\ufffe-\uffff]'
)

def get_excel_format_value(value):
    from corehq.apps.export.models.new import ExcelFormatValue

    if isinstance(value, bool):
        return ExcelFormatValue(numbers.FORMAT_GENERAL, value)
    if isinstance(value, int):
        return ExcelFormatValue(numbers.FORMAT_NUMBER, value)
    if isinstance(value, float):
        return ExcelFormatValue(numbers.FORMAT_NUMBER_00, value)
    if isinstance(value, Decimal):
        return ExcelFormatValue(numbers.FORMAT_NUMBER_00, float(value))
    if isinstance(value, datetime.datetime):
        return ExcelFormatValue(numbers.FORMAT_DATE_DATETIME, value)
    if isinstance(value, datetime.date):
        return ExcelFormatValue(numbers.FORMAT_DATE_YYYYMMDD2, value)
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    elif value is None:
        return ExcelFormatValue(numbers.FORMAT_TEXT, EMPTY_VALUE)

    if value == MISSING_VALUE or value == EMPTY_VALUE:
        return ExcelFormatValue(numbers.FORMAT_TEXT, value)

    # make sure value is string and strip whitespace before applying any
    # string operations
    value = str(value).strip()

    if value.lower() in ['true', 'false']:
        return ExcelFormatValue(
            numbers.FORMAT_GENERAL, bool(value.lower() == 'true')
        )

    # potential full date of any format
    if re.search(r"^\d+(/|-|\.)\d+(/|-|\.)\d+$", value):
        try:
            # always use standard yyy-mm-dd format for excel
            date_val = dateutil.parser.parse(value)
            # Last chance at catching an errored date. If the date is invalid,
            # yet somehow passed the regex, it will fail at this line with a
            # ValueError:
            date_val.isoformat()
            return ExcelFormatValue(numbers.FORMAT_DATE_YYYYMMDD2, date_val)
        except (ValueError, OverflowError):
            pass

    # potential time of any format
    if re.search(r"^((\d+(:))+)\d+(\.\d+((-+)((\d+(:))*)\d+)?)?(( )*[ap]m)?$",
                 value.lower()):
        try:
            # we are not returning this as a datetime object, otherwise
            # it will try to attach today's date to the value and also
            # strip the timezone information from the end
            return ExcelFormatValue(numbers.FORMAT_DATE_TIME4, value)
        except (ValueError, OverflowError):
            pass

    # potential datetime format
    if re.match(r"^\d+(/|-|\.)\d+(/|-|\.)\d+ "
                r"((\d+(:))+)\d+(\.\d+((-+)((\d+(:))*)\d+)?)?(( )*[ap]m)?$",
                value.lower()):
        try:
            # always use standard yyy-mm-dd h:mm:ss format for excel
            return ExcelFormatValue(numbers.FORMAT_DATE_DATETIME, dateutil.parser.parse(value))
        except (ValueError, OverflowError):
            pass

    # datetime ISO format (couch datetimes)
    if re.match(r"^\d{4}(-)\d{2}(-)\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$", value):
        try:
            # always use standard yyy-mm-dd h:mm:ss format for excel
            return ExcelFormatValue(numbers.FORMAT_DATE_DATETIME,
                                    dateutil.parser.parse(value))
        except (ValueError, OverflowError):
            pass

    # integer
    if re.match(r"^[+-]?\d+$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER, int(value))
        except OverflowError:
            return ExcelFormatValue(numbers.FORMAT_GENERAL, value)
        except ValueError:
            pass

    # decimal, US-style
    if re.match(r"^[+-]?\d+(\.)\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_00, float(value))
        except ValueError:
            pass

    # decimal, EURO-style
    if re.match(r"^[+-]?\d+(,)\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_00, float(value.replace(',', '.')))
        except (ValueError, OverflowError):
            pass

    # percentage without decimals
    if re.match(r"^[+-]?\d+%$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_PERCENTAGE,
                                    float(int(value.replace('%', '')) / 100))
        except (ValueError, OverflowError):
            pass

    # percentage with decimals
    if re.match(r"^[+-]?\d+(\.)\d*%$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_PERCENTAGE_00,
                                    float(float(value.replace('%', '')) / 100))
        except (ValueError, OverflowError):
            pass

    # comma-separated US-style '#,##0.00' (regexlib.com)
    if re.match(r"^(\d|-)?(\d|,)*\.?\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_COMMA_SEPARATED1,
                                    float(value.replace(',', '')))
        except (ValueError, OverflowError):
            pass

    # decimal-separated Euro-style '#.##0,00' (regexlib.com
    if re.match(r"^(\d|-)?(\d|\.)*,?\d*$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_NUMBER_COMMA_SEPARATED2,
                                    float(value.replace('.', '').replace(',', '.')))
        except (ValueError, OverflowError):
            pass

    # USD with leading zeros (regexlib.com)
    if re.match(r"^(-)?\$([1-9]{1}[0-9]{0,2}(\,[0-9]{3})*(\.\d*)?)$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_CURRENCY_USD_SIMPLE,
                                    float(value.replace(',', '').replace('$', '')))
        except (ValueError, OverflowError):
            pass

    # EURO with leading zeros (regexlib.com)
    if re.match(r"^(-)?\€([1-9]{1}[0-9]{0,2}(\.[0-9]{3})*(\,\d*)?)$", value):
        try:
            return ExcelFormatValue(numbers.FORMAT_CURRENCY_EUR_SIMPLE,
                                    float(value.replace('.', '').replace(',', '.').replace('€', '')))
        except (ValueError, OverflowError):
            pass

    # no formats matched...clean and return as text
    value = _dirty_chars.sub('?', value)
    return ExcelFormatValue(numbers.FORMAT_TEXT, value)


def get_legacy_excel_safe_value(value):
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    elif value is not None:
        value = str(value)
    else:
        value = ''
    return _dirty_chars.sub('?', value)
