import json
from unittest.mock import patch
from django.test import SimpleTestCase
from corehq.apps.data_interfaces.forms import CaseRuleCriteriaForm
from corehq.apps.data_interfaces import forms


class CaseRuleCriteriaFormTests(SimpleTestCase):
    def test_validation_with_fully_specified_location(self):
        post_data = self._create_form_input(location_filter={
            'name': 'TestLocation',
            'location_id': '123',
            'include_child_locations': False,
        })

        form = CaseRuleCriteriaForm('test-domain', post_data, rule=None)
        form.is_valid()

    def test_form_is_valid_without_location(self):
        post_data = self._create_form_input(location_filter='')

        form = CaseRuleCriteriaForm('test-domain', post_data, rule=None)
        self.assertTrue(form.is_valid())

    def setUp(self):
        case_types_patcher = patch.object(forms, 'get_case_types_for_domain')
        self.get_case_types = case_types_patcher.start()
        self.get_case_types.return_value = ['test-case']
        self.addCleanup(case_types_patcher.stop)

    def _create_form_input(self, location_filter=None):
        return {
            'criteria-case_type': 'test-case',
            'criteria-property_match_definitions': json.dumps([
                {
                    'property_name': 'city',
                    'property_value': 'Boston',
                    'match_type': 'EQUAL'
                }
            ]),
            'criteria-custom_match_definitions': json.dumps([]),
            'criteria-location_filter_definition': json.dumps(location_filter or ''),
            'criteria-ucr_filter_definitions': json.dumps([]),
            'criteria-criteria_operator': 'ALL',
            'criteria-filter_on_server_modified': 'false',
            'criteria-server_modified_boundary': '',
            'criteria-filter_on_closed_parent': 'false',
        }
