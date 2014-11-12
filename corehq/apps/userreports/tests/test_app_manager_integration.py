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
        self.assertEqual(1, len(data_sources))
        data_source = data_sources['ticket']
        self.assertEqual(app.domain, data_source.domain)
        self.assertEqual('CommCareCase', data_source.referenced_doc_type)
        self.assertEqual('ticket', data_source.table_id)
        self.assertEqual('ticket', data_source.display_name)

        # test the filter
        generated_filter = data_source.filter
        self.assertTrue(generated_filter.filter({'doc_type': 'CommCareCase', 'domain': app.domain, 'type': 'ticket'}))
        self.assertFalse(generated_filter.filter({'doc_type': 'CommCareCase', 'domain': 'wrong domain', 'type': 'ticket'}))
        self.assertFalse(generated_filter.filter({'doc_type': 'NotCommCareCase', 'domain': app.domain, 'type': 'ticket'}))
        self.assertFalse(generated_filter.filter({'doc_type': 'CommCareCase', 'domain': app.domain, 'type': 'not-ticket'}))

        # check the indicators
        expected_columns = ["doc_id", "category", "priority", "starred", "estimate"]
        for i, col in enumerate(expected_columns):
            col_back = data_source.get_columns()[i]
            self.assertEqual(col, col_back.id)

        sample_doc = dict(
            _id='some-doc-id',
            # opened_on=date_opened,
            # owner_id='some-user-id',
            doc_type="CommCareCase",
            domain=app.domain,
            type='ticket',
            category='bug',
            priority='4',
            starred='yes',
            estimate=2,
        )
        def _get_column_property(column):
            return result.column.id if result.column.id != 'doc_id' else '_id'

        for result in data_source.get_values(sample_doc):
            self.assertEqual(sample_doc[_get_column_property(result.column)], result.value)
