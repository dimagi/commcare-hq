import doctest
from mock import patch

from django.test import TestCase
from datetime import date
from nose.tools import assert_equal
from custom.onse import tasks
from custom.onse.tasks import _update_facility_cases_from_dhis2_data_elements
from corehq.motech.models import ConnectionSettings
from requests import RequestException
from celery.exceptions import MaxRetriesExceededError


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
    @patch('custom.onse.tasks.check_server_status', return_value={'ready': False, 'error': RequestException})
    def test_retry(self, *args):
        task = _update_facility_cases_from_dhis2_data_elements.delay(None, True)
        assert task.result.__class__ == MaxRetriesExceededError
