import re
from unittest import TestCase

from custom.icds.form_processor.steps import AADHAAR_XFORM_SUBMISSION_PATTERNS


class TestAadhaarPattern(TestCase):
    def test_aadhaar_number_pattern(self):
        aadhaar_number_pattern = AADHAAR_XFORM_SUBMISSION_PATTERNS[0]
        matches = re.findall(aadhaar_number_pattern, "<aadhar_number>123456789012</aadhar_number>")
        self.assertEqual(matches, ['123456789012'])
        matches = re.findall(aadhaar_number_pattern, "<aadhar_number>12345678901</aadhar_number>")
        self.assertEqual(matches, [])
