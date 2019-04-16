from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import datetime

from testil import eq

from corehq.apps.saved_reports.scheduled import _round_datetime_up_to_the_nearest_minute, \
    _iter_15_minute_marks_in_range


def test_round_datetime_up_to_the_nearest_minute():
    cases = [
        (
            'a normal time should round up',
            datetime.datetime(2019, 3, 22, 15, 6, 57, 932998),
            datetime.datetime(2019, 3, 22, 15, 7, 0, 0),
        ),
        (
            'a perfectly round time should remain unchanged',
            datetime.datetime(2019, 3, 22, 15, 7, 0, 0),
            datetime.datetime(2019, 3, 22, 15, 7, 0, 0),
        ),
        (
            'a second after a perfectly round time should still round up',
            datetime.datetime(2019, 3, 22, 15, 7, 1, 0),
            datetime.datetime(2019, 3, 22, 15, 8, 0, 0),
        ),
        (
            'a second before a perfectly round time should round up',
            datetime.datetime(2019, 3, 22, 15, 8, 59, 0),
            datetime.datetime(2019, 3, 22, 15, 9, 0, 0),
        ),
        (
            'a microsecond after a perfectly round time should still round up',
            datetime.datetime(2019, 3, 22, 15, 7, 0, 1),
            datetime.datetime(2019, 3, 22, 15, 8, 0, 0),
        ),
        (
            'a microsecond before a perfectly round time should round up',
            datetime.datetime(2019, 3, 22, 15, 8, 0, 999999),
            datetime.datetime(2019, 3, 22, 15, 9, 0, 0),
        ),
    ]

    for description, value, expected_output in cases:
        eq(_round_datetime_up_to_the_nearest_minute(value), expected_output, description)


def test_iter_15_minute_marks_in_range():
    cases = [
        (
            'a range containing one 15-minute mark should have one mark returned',
            datetime.datetime(2019, 3, 22, 15, 6, 57, 932998),
            datetime.datetime(2019, 3, 22, 15, 16, 23, 978587),
            [
                datetime.datetime(2019, 3, 22, 15, 15, 0, 0),
            ],
        ),
        (
            'a range containing no 15-minute marks should return an empty list',
            datetime.datetime(2019, 3, 22, 15, 6, 57, 932998),
            datetime.datetime(2019, 3, 22, 15, 14, 23, 978587),
            [],
        ),
        (
            'a long range should contain multiple 15-minute marks',
            datetime.datetime(2019, 3, 22, 15, 6, 57, 932998),
            datetime.datetime(2019, 3, 22, 15, 46, 23, 978587),
            [
                datetime.datetime(2019, 3, 22, 15, 15, 0, 0),
                datetime.datetime(2019, 3, 22, 15, 30, 0, 0),
                datetime.datetime(2019, 3, 22, 15, 45, 0, 0),
            ],
        ),
        (
            'with perfectly round start/end times only the start should be inclusive',
            datetime.datetime(2019, 3, 22, 15, 0, 0, 0),
            datetime.datetime(2019, 3, 22, 15, 15, 0, 0),
            [
                datetime.datetime(2019, 3, 22, 15, 0, 0, 0),
            ],
        ),
        (
            """
            if start and end are the same perfectly round time, should contain no marks

            this is because if you have times x < y, and you run (x, x) followed by (x, y),
            x would be contained in the second one, so you don't want it contained in the first
            """,
            datetime.datetime(2019, 3, 22, 15, 0, 0, 0),
            datetime.datetime(2019, 3, 22, 15, 0, 0, 0),
            [],
        ),
        (
            'if start and end are the same non-round time, should contain no marks',
            datetime.datetime(2019, 3, 22, 15, 46, 23, 978587),
            datetime.datetime(2019, 3, 22, 15, 46, 23, 978587),
            [],
        ),
    ]

    for description, start_datetime, end_datetime, expected_output in cases:
        eq(list(_iter_15_minute_marks_in_range(start_datetime, end_datetime)), expected_output,
           description)
