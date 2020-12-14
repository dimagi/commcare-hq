from datetime import date

from nose.tools import assert_equal

from corehq.motech.dhis2.const import (
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
)
from corehq.motech.dhis2.models import DataSetMap


def test_should_send_on_date():
    kwargs_day_result = [
        (
            {'frequency': SEND_FREQUENCY_WEEKLY, 'day_to_send': 5},
            date(2020, 9, 4),
            True,  # Friday Sep 4, 2020 is the 5th day of the week
        ),
        (
            {'frequency': SEND_FREQUENCY_WEEKLY, 'day_to_send': 5},
            date(2020, 9, 5),
            False,  # Saturday Sep 5, 2020 is not the 5th day of the week
        ),
        (
            {'frequency': SEND_FREQUENCY_MONTHLY, 'day_to_send': 5},
            date(2020, 9, 5),
            True,  # Sep 5 is the 5th day of the month
        ),
        (
            {'frequency': SEND_FREQUENCY_MONTHLY, 'day_to_send': 5},
            date(2020, 9, 4),
            False,  # Sep 4 is not the 5th day of the month
        ),
        (
            {'frequency': SEND_FREQUENCY_QUARTERLY, 'day_to_send': 5},
            date(2020, 7, 5),
            True,  # Jul 5 is the 5th day of the quarter
        ),
        (
            {'frequency': SEND_FREQUENCY_QUARTERLY, 'day_to_send': 5},
            date(2020, 9, 5),
            False,  # Sep 5 is not the 5th day of the quarter
        ),
    ]
    for kwargs, day, expected_result in kwargs_day_result:
        dataset_map = DataSetMap(**kwargs)
        result = dataset_map.should_send_on_date(day)
        assert_equal(result, expected_result)
