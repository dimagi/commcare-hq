from __future__ import absolute_import
from __future__ import unicode_literals

import os

from django.test import SimpleTestCase

from corehq.apps.userreports.models import get_datasource_config
from corehq.form_processor.utils import convert_xform_to_json
from corehq.util.test_utils import TestFileMixin

BLACKLISTED_COLUMNS = ['received_on', 'inserted_at']


class TestPNCForms(SimpleTestCase, TestFileMixin):
    ucr_name = "static-icds-cas-static-postnatal_care_forms"
    domain = 'icds-cas'
    file_path = ('data', )
    root = os.path.dirname(__file__)
    maxDiff = None

    def test_ebf_form(self):
        config, _ = get_datasource_config(self.ucr_name, 'icds-cas')
        config.configured_indicators = [
            ind for ind in config.configured_indicators if ind['column_id'] != 'state_id'
        ]
        form_json = convert_xform_to_json(self.get_xml('ebf_form_v10326'))
        form_json = {
            'form': form_json,
            'domain': self.domain,
            'xmlns': form_json['@xmlns'],
            'doc_type': 'XFormInstance',
        }
        ucr_result = config.get_all_values(form_json)
        for row in ucr_result:
            row = {
                i.column.database_column_name: i.value
                for i in row
                if i.column.database_column_name not in BLACKLISTED_COLUMNS
            }

            self.assertEqual({
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "ccs_record_case_id": "d53c940c-3bf3-44f7-97a1-f43fcbe74359",
                "child_health_case_id": "03f39da4-8ea3-4108-b8a8-1b58fdb4a698",
                "counsel_adequate_bf": None,
                "counsel_breast": None,
                "counsel_exclusive_bf": None,
                "counsel_increase_food_bf": None,
                "counsel_methods": None,
                "counsel_only_milk": 1,
                "skin_to_skin": None,
                "is_ebf": 1,
                "water_or_milk": 0,
                "other_milk_to_child": None,
                "tea_other": 0,
                "eating": 0,
                "not_breastfeeding": None
            }, row)

    def test_pnc_form(self):
        config, _ = get_datasource_config(self.ucr_name, 'icds-cas')
        config.configured_indicators = [
            ind for ind in config.configured_indicators if ind['column_id'] != 'state_id'
        ]
        form_json = convert_xform_to_json(self.get_xml('pnc_form_v10326'))
        form_json = {
            'form': form_json,
            'domain': self.domain,
            'xmlns': form_json['@xmlns'],
            'doc_type': 'XFormInstance',
        }
        ucr_result = config.get_all_values(form_json)
        for row in ucr_result:
            row = {
                i.column.database_column_name: i.value
                for i in row
                if i.column.database_column_name not in BLACKLISTED_COLUMNS
            }

            self.assertEqual({
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "ccs_record_case_id": "081cc405-5598-430f-ac8f-39cc4a1fdb30",
                "child_health_case_id": "252d8e20-c698-4c94-a5a9-53bbf8972b64",
                "counsel_adequate_bf": None,
                "counsel_breast": None,
                "counsel_exclusive_bf": 1,
                "counsel_increase_food_bf": 1,
                "counsel_methods": None,
                "counsel_only_milk": None,
                "skin_to_skin": None,
                "is_ebf": 1,
                "water_or_milk": None,
                "other_milk_to_child": 0,
                "tea_other": None,
                "eating": None,
                "not_breastfeeding": None
            }, row)
