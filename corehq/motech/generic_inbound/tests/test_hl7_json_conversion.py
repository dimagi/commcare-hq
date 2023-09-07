import os

from django.test import SimpleTestCase

from corehq.motech.generic_inbound.backend.hl7 import hl7_str_to_dict
from corehq.util.test_utils import TestFileMixin


class TestHL7ToJson(SimpleTestCase, TestFileMixin):
    """Test messages from https://confluence.hl7.org/display/OO/v2+Sample+Messages"""
    file_path = ('data',)
    root = os.path.dirname(__file__)

    maxDiff = None

    def test_oru_ro1(self):
        self._test_message_conversion('oru_r01_2.5.1')

    def test_adt_ao1(self):
        self._test_message_conversion('adt_a01_2.8')

    def _test_message_conversion(self, name):
        message = self.get_file(name, 'er7')
        hl7_dict = hl7_str_to_dict(message, False)
        # uncomment this to update the JSON output files
        # with open(self.get_path(name, '.json'), 'w') as f:
        #     import json
        #     json.dump(hl7_dict, f, indent=2)
        expected = self.get_json(name)
        self.assertDictEqual(hl7_dict, expected)
