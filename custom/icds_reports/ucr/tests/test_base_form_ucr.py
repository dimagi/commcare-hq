from __future__ import absolute_import
from __future__ import unicode_literals

import os

from django.test import SimpleTestCase
from mock import patch

from corehq.apps.userreports.models import get_datasource_config
from corehq.form_processor.utils import convert_xform_to_json
from corehq.util.test_utils import TestFileMixin

BLACKLISTED_COLUMNS = ('received_on', 'inserted_at')
LOCATION_COLUMNS = ('state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id')


class BaseFormsTest(SimpleTestCase, TestFileMixin):
    ucr_name = None
    domain = 'icds-cas'
    file_path = ('data', )
    root = os.path.dirname(__file__)
    maxDiff = None

    @patch('corehq.apps.callcenter.data_source.get_call_center_domains', lambda: [])
    def _get_config(self):
        config, _ = get_datasource_config(self.ucr_name, self.domain)
        config.configured_indicators = [
            ind for ind in config.configured_indicators if ind['column_id'] not in LOCATION_COLUMNS
        ]
        return config

    def _get_form_json(self, xml_file):
        form_json = convert_xform_to_json(self.get_xml(xml_file))
        return {
            'form': form_json,
            'domain': self.domain,
            'xmlns': form_json['@xmlns'],
            'doc_type': 'XFormInstance',
        }

    def _test_data_source_results(self, xml_file, expected_rows):
        config = self._get_config()
        form_json = self._get_form_json(xml_file)
        ucr_result = config.get_all_values(form_json)
        self.assertEqual(len(ucr_result), len(expected_rows))
        self.assertEqual(expected_rows, [
            {
                i.column.database_column_name: i.value
                for i in row
                if i.column.database_column_name not in BLACKLISTED_COLUMNS
            }
            for row in ucr_result
        ])
