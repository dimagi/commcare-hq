import json
import os
from django.test import TestCase
from casexml.apps.case.models import CommCareCase


class WVTest(TestCase):

    file_name = ''

    def setUp(self):
        fullpath = os.path.join(os.path.dirname(__file__), 'data', self.file_name)
        with open(fullpath, 'r') as f:
            raw = f.read()
            self.case = CommCareCase.wrap(json.loads(raw))