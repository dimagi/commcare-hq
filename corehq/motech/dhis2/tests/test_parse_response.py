import os

from django.test import SimpleTestCase

from corehq.motech.dhis2.parse_response import get_errors
from corehq.util.test_utils import TestFileMixin


class GetErrorTests(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_imported(self):
        response_json = self.get_json('imported')
        errors = get_errors(response_json["response"])
        self.assertEqual(errors, {})

    def test_ignored(self):
        response_json = self.get_json('ignored')
        errors = get_errors(response_json["response"])
        self.assertEqual(errors, {
            "enrollments.importSummaries.[0].events.importSummaries.[0].description": "Event date is required. "
        })
