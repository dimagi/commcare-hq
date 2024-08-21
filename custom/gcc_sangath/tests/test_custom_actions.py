import doctest
from datetime import date
from unittest.mock import patch

from nose.tools import assert_equal

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.tests.test_auto_case_updates import (
    BaseCaseRuleTest,
)
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.form_processor.models import CommCareCase
from custom.gcc_sangath.const import (
    DATE_OF_PEER_REVIEW_CASE_PROP,
    MEAN_GENERAL_SKILLS_SCORE_CASE_PROP,
    MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP,
    NEEDS_AGGREGATION_CASE_PROP,
    NEEDS_AGGREGATION_NO_VALUE,
    PEER_RATING_CASE_TYPE,
    SESSION_CASE_TYPE,
    SESSION_RATING_CASE_PROP,
)
from custom.gcc_sangath.rules.custom_actions import (
    _get_aggregate,
    _get_count,
    _get_sum,
    sanitize_session_peer_rating,
)


class SanitizeSessionPeerRatingTest(BaseCaseRuleTest):
    domain = 'gcc-sangath'

    @patch('custom.gcc_sangath.rules.custom_actions.update_case')
    def test_with_no_peer_rating_cases(self, update_case_mock):
        rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type=SESSION_CASE_TYPE,
        )
        session_case = CaseFactory(self.domain).create_case(
            case_type=SESSION_CASE_TYPE,
        )

        result = sanitize_session_peer_rating(session_case, rule)

        update_case_mock.assert_not_called()
        self.assertEqual(result.num_updates, 0)

    def test_with_empty_peer_rating_cases(self):
        rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type=SESSION_CASE_TYPE,
        )
        self._set_up_cases([{}])

        result = sanitize_session_peer_rating(self.session_case, rule)

        self.assertEqual(result.num_updates, 1)
        session_case = CommCareCase.objects.get_case(self.session_case.case_id, self.session_case.domain)
        self.assertDictEqual(
            session_case.case_json,
            {
                'agg_mean_general_skills_score': '0.0',
                'agg_mean_treatment_specific_score': '0.0',
                'agg_rating': '0.0',
                'date_of_peer_review': '',
                'feedback_num': '1',
                'share_score_check': 'yes',
                'total_session_rating': '0.0',
                NEEDS_AGGREGATION_CASE_PROP: NEEDS_AGGREGATION_NO_VALUE,
            }
        )

    def test_with_peer_rating_cases(self):
        rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type=SESSION_CASE_TYPE,
        )
        self._set_up_cases([
            {
                MEAN_GENERAL_SKILLS_SCORE_CASE_PROP: 1.5,
                MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP: 2.3,
                SESSION_RATING_CASE_PROP: 3.7,
                DATE_OF_PEER_REVIEW_CASE_PROP: date(2020, 1, 1)
            },
            {
                MEAN_GENERAL_SKILLS_SCORE_CASE_PROP: 2,
                MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP: 3.3,
                SESSION_RATING_CASE_PROP: 5.2,
                DATE_OF_PEER_REVIEW_CASE_PROP: date(2020, 8, 10)
            },
            {
                MEAN_GENERAL_SKILLS_SCORE_CASE_PROP: 1.8,
                MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP: 2,
                SESSION_RATING_CASE_PROP: 4,
                DATE_OF_PEER_REVIEW_CASE_PROP: date(2020, 3, 10)
            },
            {
                MEAN_GENERAL_SKILLS_SCORE_CASE_PROP: 1.9,
                MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP: 2.9,
                SESSION_RATING_CASE_PROP: 4,
                DATE_OF_PEER_REVIEW_CASE_PROP: date(2020, 3, 10)
            },
        ])

        result = sanitize_session_peer_rating(self.session_case, rule)

        self.assertEqual(result.num_updates, 1)
        session_case = CommCareCase.objects.get_case(self.session_case.case_id, self.session_case.domain)
        self.assertDictEqual(
            session_case.case_json,
            {
                'agg_mean_general_skills_score': '1.8',
                'agg_mean_treatment_specific_score': '2.6',
                'agg_rating': '4.2',
                'date_of_peer_review': '2020-08-10',
                'feedback_num': '4',
                'share_score_check': 'yes',
                'total_session_rating': '16.9',
                NEEDS_AGGREGATION_CASE_PROP: NEEDS_AGGREGATION_NO_VALUE,
            }
        )

    def _set_up_cases(self, peer_ratings_case_json=None):
        peer_ratings_case_json = peer_ratings_case_json or []
        session_case = CaseStructure(
            attrs={
                'create': True,
                'case_type': SESSION_CASE_TYPE,
                'update': {
                    "name": "Session 1",
                },
            })
        extension_cases = []
        for peer_rating_case_json in peer_ratings_case_json:
            case_json = {'name': "Peer Rating"}
            case_json.update(peer_rating_case_json)
            extension_cases.append(CaseStructure(
                attrs={
                    'create': True,
                    'case_type': PEER_RATING_CASE_TYPE,
                    'update': case_json,
                },
                indices=[CaseIndex(
                    session_case,
                    identifier='parent',
                    relationship='extension',
                )],
            ))

        # also set up an unknown case type to test only peer_rating cases are used
        extension_cases.append(CaseStructure(
            attrs={
                'create': True,
                'case_type': 'unknown',
            },
            indices=[CaseIndex(
                session_case,
                identifier='parent',
                relationship='extension',
            )],
        ))

        cases = CaseFactory(self.domain).create_or_update_cases(extension_cases)
        self.session_case = cases[-1]


def test_doctests():
    import custom.gcc_sangath.rules.custom_actions as module

    results = doctest.testmod(module)
    assert results.failed == 0


class MockCase(dict):
    def get_case_property(self, prop):
        return self[prop]


peer_rating_cases = [
    MockCase({SESSION_RATING_CASE_PROP: 1.1}),
    MockCase({SESSION_RATING_CASE_PROP: '2.2'}),
    MockCase({SESSION_RATING_CASE_PROP: 10 / 3}),
    MockCase({SESSION_RATING_CASE_PROP: ' '}),
]


def test_get_sum():
    total = _get_sum(SESSION_RATING_CASE_PROP, peer_rating_cases)
    assert_equal(total, 6.633333333333334)


def test_get_count():
    count = _get_count(SESSION_RATING_CASE_PROP, peer_rating_cases)
    assert_equal(count, 3)


def test_get_aggregate():
    aggregate = _get_aggregate(SESSION_RATING_CASE_PROP, peer_rating_cases)
    assert_equal(aggregate, 2.2)


def test_division_by_zero():
    aggregate = _get_aggregate(SESSION_RATING_CASE_PROP, [])
    assert_equal(aggregate, 0.0)
