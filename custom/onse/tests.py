import doctest
from mock import patch

from django.test import TestCase
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from nose.tools import assert_equal
from custom.onse import tasks
from custom.onse.tasks import _update_facility_cases_from_dhis2_data_elements
from corehq.motech.models import ConnectionSettings
from requests import RequestException


def test_previous_quarter():
    test_dates = [
        (date(2020, 1, 1), '2019Q4'),
        (date(2020, 3, 31), '2019Q4'),
        (date(2020, 4, 1), '2020Q1'),
        (date(2020, 6, 30), '2020Q1'),
        (date(2020, 7, 1), '2020Q2'),
        (date(2020, 9, 30), '2020Q2'),
        (date(2020, 10, 1), '2020Q3'),
        (date(2020, 12, 31), '2020Q3'),
    ]
    for test_date, expected_value in test_dates:
        assert_equal(tasks.previous_quarter(test_date), expected_value)


def test_doctests():
    results = doctest.testmod(tasks)
    assert results.failed == 0


class TestUpdateFromDhis2Task(TestCase):

    @patch('custom.onse.tasks.domain_exists', return_value=True)
    @patch('custom.onse.tasks.get_dhis2_server', return_value=ConnectionSettings())
    @patch('custom.onse.tasks._check_server_status', return_value={'ready': False, 'error': RequestException})
    @patch('custom.onse.tasks._schedule_execution')
    def test_retry(self, *args):
        _update_facility_cases_from_dhis2_data_elements(None, True)

        schedule_execution_function = args[0]
        list_of_schedule_execution_function_calls = schedule_execution_function.call_args_list
        first_call_with_args = list_of_schedule_execution_function_calls[0]
        call_args = first_call_with_args[0]

        callback_function = call_args[0]
        callback_function_args = call_args[1]
        callback_function_execution_date = call_args[2]

        expected_execution_date = datetime.utcnow() + relativedelta(days=1)

        assert callback_function == _update_facility_cases_from_dhis2_data_elements
        assert callback_function_args == [None, True, 1]
        assert callback_function_execution_date.date() == expected_execution_date.date()
