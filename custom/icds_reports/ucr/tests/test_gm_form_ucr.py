from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestGMForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-dashboard_growth_monitoring_forms"

    def test_advanced_gm_form(self):
        self._test_data_source_results(
            'advanced_gm_form_v10326',
            [{
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "child_health_case_id": "3fb53b1f-605c-4cfd-89c6-f0e72988f9bc",
                "weight_child": 6,
                "height_child": 120.0,
                "zscore_grading_wfa": 0,
                "zscore_grading_hfa": 3,
                "zscore_grading_wfh": 1,
                "muac_grading": 2,
            }])

    def test_gm_form(self):
        self._test_data_source_results(
            'gm_form_v10326',
            [{
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "child_health_case_id": "a4f7beff-5995-4155-be9c-ab2f7ec2c91c",
                "weight_child": 3,
                "height_child": None,
                "zscore_grading_wfa": 1,
                "zscore_grading_hfa": 0,
                "zscore_grading_wfh": 0,
                "muac_grading": 0,
            }])

    def test_delivery_form(self):
        self._test_data_source_results(
            'delivery_form_v10326',
            [{
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "child_health_case_id": "00cabe2c-df9e-4520-a943-837ec5b4559b",
                "weight_child": 3,
                "height_child": None,
                "zscore_grading_wfa": 3,
                "zscore_grading_hfa": 0,
                "zscore_grading_wfh": 0,
                "muac_grading": 0,
            }])
