from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestDailyFeedingForms(BaseFormsTest):
    ucr_name = "static-icds-cas-dashboard_child_health_daily_feeding_forms"

    def test_daily_feeding_form(self):
        self._test_data_source_results(
            'daily_feeding_form_v10326', [
                {
                    "doc_id": None,
                    "repeat_iteration": 0,
                    "timeend": None,
                    "child_health_case_id": "5e146742-dd02-4e00-b24a-810a504eb4d7",
                    "eligible": 1,
                    "active": 1,
                    "attended_child_ids": 1,
                    "breakfast": 1,
                    "lunch": 0,
                    "double_meal": 0,
                },
                {
                    "doc_id": None,
                    "repeat_iteration": 1,
                    "timeend": None,
                    "child_health_case_id": "ad36920b-2a95-4a9f-affc-dec8a58ff920",
                    "eligible": 1,
                    "active": 1,
                    "attended_child_ids": 1,
                    "breakfast": 1,
                    "lunch": 1,
                    "double_meal": 0,
                },
                {
                    "doc_id": None,
                    "repeat_iteration": 2,
                    "timeend": None,
                    "child_health_case_id": "85bfde91-44b8-4eca-bcca-47d1f97c6d1b",
                    "eligible": 1,
                    "active": 1,
                    "attended_child_ids": 1,
                    "breakfast": 1,
                    "lunch": 1,
                    "double_meal": 0,
                },
                {
                    "doc_id": None,
                    "repeat_iteration": 3,
                    "timeend": None,
                    "child_health_case_id": "57180c28-91d8-4b3b-8618-67b757467069",
                    "eligible": 1,
                    "active": 1,
                    "attended_child_ids": 1,
                    "breakfast": 0,
                    "lunch": 1,
                    "double_meal": 0,
                },
                {
                    "doc_id": None,
                    "repeat_iteration": 4,
                    "timeend": None,
                    "child_health_case_id": "a2b3ff4d-2b84-4d43-851a-538576b4e1ea",
                    "eligible": 1,
                    "active": 1,
                    "attended_child_ids": 1,
                    "breakfast": 1,
                    "lunch": 1,
                    "double_meal": 0,
                },
            ])
