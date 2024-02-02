import pytz
from datetime import date, datetime
from unittest.mock import patch
from django.test import TestCase

from corehq.apps.case_search.utils import get_expanded_case_results
from corehq.apps.case_search.xpath_functions.comparison import adjust_to_utc
from corehq.form_processor.models import CommCareCase


@patch("corehq.apps.case_search.utils._get_case_search_cases")
def test_get_expanded_case_results(get_cases_mock):
    cases = [
        CommCareCase(case_json={}),
        CommCareCase(case_json={"potential_duplicate_id": "123"}),
        CommCareCase(case_json={"potential_duplicate_id": "456"}),
        CommCareCase(case_json={"potential_duplicate_id": ""}),
        CommCareCase(case_json={"potential_duplicate_id": None}),
    ]
    helper = None
    get_expanded_case_results(helper, "potential_duplicate_id", cases)
    get_cases_mock.assert_called_with(helper, {"123", "456"})


class TestTimezoneAdjustment(TestCase):

    def test_user_input_timezone_adjustment_forward(self):
        self.timezone = pytz.timezone('Asia/Seoul')  # UTC+09:00
        self.assertEqual(datetime(2023, 6, 3, 15, 0, 0),
                         adjust_to_utc(date(2023, 6, 4), self.timezone))

    def test_user_input_timezone_adjustment_backward(self):
        self.timezone = pytz.timezone('US/Hawaii')  # UTC+10:00
        self.assertEqual(datetime(2023, 6, 4, 10, 0, 0),
                         adjust_to_utc(date(2023, 6, 4), self.timezone))
