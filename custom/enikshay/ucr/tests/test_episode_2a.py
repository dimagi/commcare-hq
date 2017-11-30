from __future__ import absolute_import

from corehq.apps.userreports.specs import EvaluationContext
from custom.enikshay.ucr.tests.util import TestDataSourceExpressions

EPISODE_DATA_SOURCE = 'episode_v4.json'


class TestEpisode2B(TestDataSourceExpressions):

    data_source_name = EPISODE_DATA_SOURCE

    def test_presumptive_tb_episode_with_one_occurrence(self):
        episode_case_one = {
            '_id': 'episode_case_one_id',
            'domain': 'enikshay-test',
            'episode_type': 'presumptive_tb',
            'indices': [
                {'referenced_id': 'occurrence_case_one_id'}
            ]
        }

        episode_case_two = {
            '_id': 'episode_case_two_id',
            'domain': 'enikshay-test',
            'episode_type': 'other_type',
            'indices': [
                {'referenced_id': 'occurrence_case_two_id'}
            ]
        }

        episode_case_three = {
            '_id': 'episode_case_three_id',
            'domain': 'enikshay-test',
            'episode_type': 'presumptive_tb',
            'indices': [
                {'referenced_id': 'occurrence_case_two_id'}
            ]
        }

        episode_case_four = {
            '_id': 'episode_case_four_id',
            'domain': 'enikshay-test',
            'episode_type': 'other_type',
            'indices': [
                {'referenced_id': 'occurrence_case_one_id'}
            ]
        }

        occurrence_case_one = {
            '_id': 'occurrence_case_one_id',
            'domain': 'enikshay-test',
            'occurrence_episode_count': 2,
        }

        occurrence_case_two = {
            '_id': 'occurrence_case_two_id',
            'domain': 'enikshay-test',
            'occurrence_episode_count': 1,
        }

        self.database.mock_docs = {
            'episode_case_one_id': episode_case_one,
            'episode_case_two_id': episode_case_two,
            'episode_case_three_id': episode_case_three,
            'episode_case_four_id': episode_case_four,
            'occurrence_case_one_id': occurrence_case_one,
            'occurrence_case_two_id': occurrence_case_two,
        }

        expression = self.get_expression('presumptive_tb_episode_with_one_occurrence', 'integer')

        self.assertEqual(expression(episode_case_one, EvaluationContext(episode_case_one, 0)), 1)
        self.assertEqual(expression(episode_case_two, EvaluationContext(episode_case_two, 0)), 0)
        self.assertEqual(expression(episode_case_three, EvaluationContext(episode_case_three, 0)), 0)
        self.assertEqual(expression(episode_case_four, EvaluationContext(episode_case_four, 0)), 0)
