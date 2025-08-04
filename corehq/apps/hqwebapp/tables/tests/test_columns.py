from django.test import SimpleTestCase

import pytz
from django_tables2 import Table

from corehq.apps.hqwebapp.tables.columns import DateTimeStringColumn


class SimpleTable(Table):
    date_col = DateTimeStringColumn()
    date_col_tz = DateTimeStringColumn(timezone=pytz.timezone('Asia/Kolkata'))
    date_col_phonetime = DateTimeStringColumn(phonetime=True)


class TestDateTimeStringColumn(SimpleTestCase):

    def test_default(self):
        table = SimpleTable([{'date_col': '2024-06-01T12:34:56Z'}])
        rendered_value = list(table.rows)[0].get_cell('date_col')
        assert rendered_value == 'Jun 01, 2024 12:34:56 UTC'

    def test_with_timezone(self):
        table = SimpleTable([{'date_col_tz': '2024-06-01T12:34:56Z'}])
        rendered_value = list(table.rows)[0].get_cell('date_col_tz')
        assert rendered_value == 'Jun 01, 2024 18:04:56 IST'

    def test_with_phonetime(self):
        table = SimpleTable([{'date_col_phonetime': '2024-06-01T12:34:56Z'}])
        rendered_value = list(table.rows)[0].get_cell('date_col_phonetime')
        assert rendered_value == 'Jun 01, 2024 12:34:56 UTC'

    def test_invalid_datetime(self):
        table = SimpleTable([{'date_col': 'not-a-date'}])
        rendered_value = list(table.rows)[0].get_cell('date_col')
        assert rendered_value == ''
