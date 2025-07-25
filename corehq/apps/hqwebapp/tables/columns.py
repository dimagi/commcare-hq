from datetime import date

import pytz
from django_tables2 import columns

from corehq.apps.reports.util import report_date_to_json
from corehq.const import USER_DATETIME_FORMAT_WITH_SEC
from corehq.util.timezones.utils import parse_date


class DateTimeStringColumn(columns.Column):
    """
    Datetime column that can be used to render dates stored as strings.
    To be used with django tables2.
    """
    def __init__(self, *args, timezone=pytz.UTC, phonetime=False, **kwargs):
        self.timezone = timezone
        self.phonetime = phonetime
        super().__init__(*args, **kwargs)

    def render(self, value):
        parsed_date = parse_date(value)
        if not isinstance(parsed_date, date):
            return ''
        return report_date_to_json(
            parsed_date,
            self.timezone,
            USER_DATETIME_FORMAT_WITH_SEC,
            is_phonetime=self.phonetime
        )
