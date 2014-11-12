import json
import os
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.userreports.app_manager import get_case_data_sources


class AppManagerDataSourceConfigTest(SimpleTestCase):

    def get_json(self, name):
        with open(os.path.join(os.path.dirname(__file__), 'data', 'app_manager', name)) as f:
            return json.loads(f.read())

    def testSimpleCaseManagement(self):
        app = Application.wrap(self.get_json('simple_app.json'))
        data_sources = get_case_data_sources(app)
        self.assertEqual(2, len(data_sources))
        brogammer_case_config = data_sources['brogrammer']
        self.assertEqual(app.domain, brogammer_case_config.domain)
        self.assertEqual('CommCareCase', brogammer_case_config.referenced_doc_type)
        # todo: add a bunch more tests for the rest of the stuff
