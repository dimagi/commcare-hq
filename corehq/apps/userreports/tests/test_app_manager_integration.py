import json
import os
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.userreports.app_manager import get_case_data_sources, \
    get_default_case_property_datatypes


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
        expected_columns = set(["doc_id", "modified_on", "user_id", "opened_on", "owner_id", "name", "category", "priority", "starred", "estimate"])
        self.assertEqual(expected_columns, set(col_back.id for col_back in data_source.get_columns()))

        sample_doc = dict(
            _id='some-doc-id',
            doc_type="CommCareCase",
            modified_on="2014-11-12T15:37:49",
            user_id="23407238074",
            opened_on="2014-11-11T23:34:34",
            owner_id="0923409230948",
            name="priority ticket",
            domain=app.domain,
            type='ticket',
            category='bug',
            priority='4',
            starred='yes',
            estimate=2,
        )
        def _get_column_property(column):
            return column.id if column.id != 'doc_id' else '_id'


        default_case_property_datatypes = get_default_case_property_datatypes()
        for result in data_source.get_values(sample_doc):
            self.assertEqual(sample_doc[_get_column_property(result.column)], result.value)
            if result.column.id in default_case_property_datatypes:
                self.assertEqual(
                    result.column.datatype,
                    default_case_property_datatypes[result.column.id]
                )
