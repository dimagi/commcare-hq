from __future__ import absolute_import
import json
import os

from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.specs import FactoryContext, EvaluationContext

TEST_DATA_SOURCE = 'test_2b_v4.json'


class TestTestCase2B(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestTestCase2B, cls).setUpClass()

        test_data_source_file = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
            'data_sources',
            TEST_DATA_SOURCE
        )

        with open(test_data_source_file) as f:
            cls.test_data_source = DataSourceConfiguration.wrap(json.loads(f.read())['config'])
            cls.named_expressions = cls.test_data_source.named_expression_objects

    def setUp(self):
        self.orig_db = CommCareCase.get_db()
        self.database = FakeCouchDb()
        CommCareCase.set_db(self.database)

    def tearDown(self):
        CommCareCase.set_db(self.orig_db)

    def _get_column(self, column_id):
        return [
            ind
            for ind in self.test_data_source.configured_indicators
            if ind['column_id'] == column_id
        ][0]

    def test_follow_up_treatment_initiation_date_month_follow_up_dstb(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-07-01',
            'archive_reason': None,
            'treatment_outcome': None,
        }

        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_case_id': 'episode_case_id',
            'rft_general': 'follow_up_dstb',
            'rft_dstb_follow_up_treatment_month': '3',
            'date_reported': '2017-10-01'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'test_case_id': test_case
        }

        column = self._get_column('follow_up_treatment_initiation_date_month')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), '3')

    def test_follow_up_treatment_initiation_date_month_follow_up_drtb(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-07-01',
            'archive_reason': None,
            'treatment_outcome': None,
        }

        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_case_id': 'episode_case_id',
            'rft_general': 'follow_up_drtb',
            'date_reported': '2017-10-01',
            'rft_drtb_follow_up_treatment_month': '6'
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'test_case_id': test_case
        }

        column = self._get_column('follow_up_treatment_initiation_date_month')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), '6')

    def test_key_populations(self):
        episode_case = {
            '_id': 'episode_case_id',
            'domain': 'enikshay-test',
            'treatment_initiation_date': '2017-09-28',
            'archive_reason': None,
            'treatment_outcome': None,
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        occurrence_case = {
            '_id': 'occurrence_case_id',
            'domain': 'enikshay-test',
            'indices': [
                {'referenced_id': 'person_case_id'}
            ],
            'key_populations': 'test test2 test3'
        }

        person_case = {
            '_id': 'person_case_id',
            'domain': 'enikshay-test',
            'owner_id': 'owner-id'
        }

        test_case = {
            '_id': 'test_case_id',
            'domain': 'enikshay-test',
            'episode_case_id': 'episode_case_id',
            'rft_general': 'follow_up_dstb',
            'date_reported': '2017-10-01',
            'indices': [
                {'referenced_id': 'occurrence_case_id'}
            ]
        }

        self.database.mock_docs = {
            'episode_case_id': episode_case,
            'occurrence_case_id': occurrence_case,
            'person_case_id': person_case,
            'test_case_id': test_case
        }

        column = self._get_column('key_populations')
        self.assertEqual(column['datatype'], 'string')
        expression = ExpressionFactory.from_spec(
            column['expression'],
            context=FactoryContext(self.named_expressions, {})
        )

        self.assertEqual(expression(test_case, EvaluationContext(test_case, 0)), 'test, test2, test3')
