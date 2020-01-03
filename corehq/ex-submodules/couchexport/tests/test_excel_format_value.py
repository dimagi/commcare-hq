import datetime

from dateutil.tz import tzoffset
from openpyxl.styles import numbers

from django.test import SimpleTestCase

from corehq.apps.export.const import MISSING_VALUE, EMPTY_VALUE
from couchexport.util import get_excel_format_value


class TestExcelFormatValue(SimpleTestCase):

    def test_integers(self):
        excel_format, value = get_excel_format_value('3423')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER)
        self.assertEqual(value, 3423)
        self.assertEqual(type(value), int)

        excel_format, value = get_excel_format_value('-234')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER)
        self.assertEqual(value, -234)
        self.assertEqual(type(value), int)

        excel_format, value = get_excel_format_value(324)
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER)
        self.assertEqual(value, 324)
        self.assertEqual(type(value), int)

    def test_decimal(self):
        excel_format, value = get_excel_format_value('4.0345')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_00)
        self.assertEqual(value, 4.0345)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('-3.234')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_00)
        self.assertEqual(value, -3.234)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value(5.032)
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_00)
        self.assertEqual(value, 5.032)
        self.assertEqual(type(value), float)

    def test_boolean(self):
        excel_format, value = get_excel_format_value('TRUE')
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, True)
        self.assertEqual(type(value), bool)

        excel_format, value = get_excel_format_value('True')
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, True)
        self.assertEqual(type(value), bool)

        excel_format, value = get_excel_format_value('true')
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, True)
        self.assertEqual(type(value), bool)

        excel_format, value = get_excel_format_value(True)
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, True)
        self.assertEqual(type(value), bool)

        excel_format, value = get_excel_format_value('FALSE')
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, False)
        self.assertEqual(type(value), bool)

        excel_format, value = get_excel_format_value('False')
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, False)
        self.assertEqual(type(value), bool)

        excel_format, value = get_excel_format_value('false')
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, False)
        self.assertEqual(type(value), bool)

        excel_format, value = get_excel_format_value(False)
        self.assertEqual(excel_format, numbers.FORMAT_GENERAL)
        self.assertEqual(value, False)
        self.assertEqual(type(value), bool)

    def test_decimal_eur(self):
        excel_format, value = get_excel_format_value('6,9234')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_00)
        self.assertEqual(value, 6.9234)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('-5,342')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_00)
        self.assertEqual(value, -5.342)
        self.assertEqual(type(value), float)

    def test_percentage(self):
        excel_format, value = get_excel_format_value('80%')
        self.assertEqual(excel_format, numbers.FORMAT_PERCENTAGE)
        self.assertEqual(value, 80)
        self.assertEqual(type(value), int)

        excel_format, value = get_excel_format_value('-50%')
        self.assertEqual(excel_format, numbers.FORMAT_PERCENTAGE)
        self.assertEqual(value, -50)
        self.assertEqual(type(value), int)

        excel_format, value = get_excel_format_value('3.45%')
        self.assertEqual(excel_format, numbers.FORMAT_PERCENTAGE_00)
        self.assertEqual(value, 3.45)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('-4.35%')
        self.assertEqual(excel_format, numbers.FORMAT_PERCENTAGE_00)
        self.assertEqual(value, -4.35)
        self.assertEqual(type(value), float)

    def test_comma_separated_us(self):
        excel_format, value = get_excel_format_value('3,000.0234')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED1)
        self.assertEqual(value, 3000.0234)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('3,234,000.342')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED1)
        self.assertEqual(value, 3234000.342)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('5,000,343')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED1)
        self.assertEqual(value, 5000343)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('-5,334.32')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED1)
        self.assertEqual(value, -5334.32)
        self.assertEqual(type(value), float)

    def test_comma_separated_eur(self):
        excel_format, value = get_excel_format_value('5.600,0322')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED2)
        self.assertEqual(value, 5600.0322)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('8.435.600,0322')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED2)
        self.assertEqual(value, 8435600.0322)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('5.555.600')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED2)
        self.assertEqual(value, 5555600)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('-2.433,032')
        self.assertEqual(excel_format, numbers.FORMAT_NUMBER_COMMA_SEPARATED2)
        self.assertEqual(value, -2433.032)
        self.assertEqual(type(value), float)

    def test_currency_usd(self):
        excel_format, value = get_excel_format_value('$3,534.02')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_USD_SIMPLE)
        self.assertEqual(value, 3534.02)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('$99')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_USD_SIMPLE)
        self.assertEqual(value, 99)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('$5,000')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_USD_SIMPLE)
        self.assertEqual(value, 5000)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('-$234.02')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_USD_SIMPLE)
        self.assertEqual(value, -234.02)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('$4.4302')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_USD_SIMPLE)
        self.assertEqual(value, 4.4302)
        self.assertEqual(type(value), float)

    def test_currency_eur(self):
        excel_format, value = get_excel_format_value('€5.323,09')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_EUR_SIMPLE)
        self.assertEqual(value, 5323.09)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('-€303,03')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_EUR_SIMPLE)
        self.assertEqual(value, -303.03)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('€22')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_EUR_SIMPLE)
        self.assertEqual(value, 22)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('€3.303')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_EUR_SIMPLE)
        self.assertEqual(value, 3303)
        self.assertEqual(type(value), float)

        excel_format, value = get_excel_format_value('€3,003')
        self.assertEqual(excel_format, numbers.FORMAT_CURRENCY_EUR_SIMPLE)
        self.assertEqual(value, 3.003)
        self.assertEqual(type(value), float)

    def test_date(self):
        excel_format, value = get_excel_format_value('2020-01-20')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_YYYYMMDD2)
        self.assertEqual(value, datetime.datetime(2020, 1, 20, 0, 0))
        self.assertEqual(type(value), datetime.datetime)

        excel_format, value = get_excel_format_value('2020/01/20')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_YYYYMMDD2)
        self.assertEqual(value, datetime.datetime(2020, 1, 20, 0, 0))
        self.assertEqual(type(value), datetime.datetime)

        excel_format, value = get_excel_format_value('2020.01.20')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_YYYYMMDD2)
        self.assertEqual(value, datetime.datetime(2020, 1, 20, 0, 0))
        self.assertEqual(type(value), datetime.datetime)

    def test_datetime(self):
        excel_format, value = get_excel_format_value('2020-01-20 12:33')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_DATETIME)
        self.assertEqual(value, datetime.datetime(2020, 1, 20, 12, 33))
        self.assertEqual(type(value), datetime.datetime)

        excel_format, value = get_excel_format_value('2020-01-20 12:33:22')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_DATETIME)
        self.assertEqual(value, datetime.datetime(2020, 1, 20, 12, 33, 22))
        self.assertEqual(type(value), datetime.datetime)

        excel_format, value = get_excel_format_value('2020-01-20 1:33:22PM')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_DATETIME)
        self.assertEqual(value, datetime.datetime(2020, 1, 20, 13, 33, 22))
        self.assertEqual(type(value), datetime.datetime)

        excel_format, value = get_excel_format_value('2020-01-20 09:33:22.890000-6:00')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_DATETIME)
        self.assertEqual(
            value,
            datetime.datetime(2020, 1, 20, 9, 33, 22, 890000,
                              tzinfo=tzoffset(None, -21600))
        )
        self.assertEqual(type(value), datetime.datetime)

        excel_format, value = get_excel_format_value('2020-01-20 09:33:22.890000-6')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_DATETIME)
        self.assertEqual(
            value,
            datetime.datetime(2020, 1, 20, 9, 33, 22, 890000,
                              tzinfo=tzoffset(None, -21600))
        )
        self.assertEqual(type(value), datetime.datetime)

    def test_time(self):
        excel_format, value = get_excel_format_value('12:33')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_TIME4)
        self.assertEqual(value, '12:33')
        self.assertEqual(type(value), str)

        excel_format, value = get_excel_format_value('12:33:66')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_TIME4)
        self.assertEqual(value, '12:33:66')
        self.assertEqual(type(value), str)

        excel_format, value = get_excel_format_value('09:33:22.890000-6:00')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_TIME4)
        self.assertEqual(value, '09:33:22.890000-6:00')
        self.assertEqual(type(value), str)

        excel_format, value = get_excel_format_value('09:33:22.890000-6')
        self.assertEqual(excel_format, numbers.FORMAT_DATE_TIME4)
        self.assertEqual(value, '09:33:22.890000-6')
        self.assertEqual(type(value), str)

    def test_missing(self):
        excel_format, value = get_excel_format_value(MISSING_VALUE)
        self.assertEqual(excel_format, numbers.FORMAT_TEXT)
        self.assertEqual(value, MISSING_VALUE)
        self.assertEqual(type(value), str)

    def test_empty(self):
        excel_format, value = get_excel_format_value(EMPTY_VALUE)
        self.assertEqual(excel_format, numbers.FORMAT_TEXT)
        self.assertEqual(value, EMPTY_VALUE)
        self.assertEqual(type(value), str)

    def test_text(self):
        excel_format, value = get_excel_format_value('hi this is text')
        self.assertEqual(excel_format, numbers.FORMAT_TEXT)
        self.assertEqual(value, 'hi this is text')
        self.assertEqual(type(value), str)

        excel_format, value = get_excel_format_value('1241234eeeesffsfs')
        self.assertEqual(excel_format, numbers.FORMAT_TEXT)
        self.assertEqual(value, '1241234eeeesffsfs')
        self.assertEqual(type(value), str)
