from datetime import date
from unittest.mock import patch

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.tests.test_auto_case_updates import (
    BaseCaseRuleTest,
)
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from corehq.form_processor.models import CommCareCase
from custom.gcc_sangath.const import (
    DATE_OF_PEER_REVIEW_CASE_PROP,
    MEAN_GENERAL_SKILLS_SCORE_CASE_PROP,
    MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP,
    PEER_RATING_CASE_TYPE,
    SESSION_CASE_TYPE,
    SESSION_RATING_CASE_PROP,
)
from custom.gcc_sangath.rules.custom_actions import (
    sanitize_session_peer_rating,
)


class SanitizeSessionPeerRatingTest(BaseCaseRuleTest):
    domain = 'gcc-sangath'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.project = create_domain(cls.domain)
        cls.addClassCleanup(cls.project.delete)

        username = normalize_username("mobile_worker_1", cls.domain)
        cls.mobile_worker = CommCareUser.create(cls.domain, username, "123", created_by=None, created_via=None)
        cls.addClassCleanup(cls.mobile_worker.delete, cls.domain, deleted_by=None, deleted_via=None)

        cls.case_factory = CaseFactory(cls.domain)

    @patch('custom.gcc_sangath.rules.custom_actions.update_case')
    def test_with_no_peer_rating_cases(self, update_case_mock):
        rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type=SESSION_CASE_TYPE,
        )
        session_case = self.case_factory.create_case(
            case_type=SESSION_CASE_TYPE,
            owner_id=self.mobile_worker.get_id,
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
                'total_session_rating': '0'
            }
        )

    def test_with_peer_rating_cases(self):
        rule = create_empty_rule(
            self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE, case_type=SESSION_CASE_TYPE,
        )
        self._set_up_cases([
            {
                MEAN_GENERAL_SKILLS_SCORE_CASE_PROP: 1,
                MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP: 2,
                SESSION_RATING_CASE_PROP: 3,
                DATE_OF_PEER_REVIEW_CASE_PROP: date(2020, 1, 1)
            },
            {
                MEAN_GENERAL_SKILLS_SCORE_CASE_PROP: 2,
                MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP: 3,
                SESSION_RATING_CASE_PROP: 5,
                DATE_OF_PEER_REVIEW_CASE_PROP: date(2020, 8, 10)
            },
            {
                MEAN_GENERAL_SKILLS_SCORE_CASE_PROP: 1,
                MEAN_TREATMENT_SPECIFIC_SCORE_CASE_PROP: 2,
                SESSION_RATING_CASE_PROP: 4,
                DATE_OF_PEER_REVIEW_CASE_PROP: date(2020, 3, 10)
            }
        ])

        result = sanitize_session_peer_rating(self.session_case, rule)

        self.assertEqual(result.num_updates, 1)
        session_case = CommCareCase.objects.get_case(self.session_case.case_id, self.session_case.domain)
        self.assertDictEqual(
            session_case.case_json,
            {
                'agg_mean_general_skills_score': '1.3',
                'agg_mean_treatment_specific_score': '2.3',
                'agg_rating': '4.0',
                'date_of_peer_review': '2020-08-10',
                'feedback_num': '3',
                'share_score_check': 'yes',
                'total_session_rating': '12'
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
        peer_rating_cases = []
        for peer_rating_case_json in peer_ratings_case_json:
            case_json = {'name': "Peer Rating"}
            case_json.update(peer_rating_case_json)
            peer_rating_cases.append(CaseStructure(
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
        cases = self.case_factory.create_or_update_cases(peer_rating_cases)
        self.session_case = cases[-1]
