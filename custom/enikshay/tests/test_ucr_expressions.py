from __future__ import absolute_import
import uuid
from django.test import TestCase, override_settings
from nose.tools import nottest

from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseIndex
from casexml.apps.case.mock import CaseStructure
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.userreports.expressions import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext
from custom.enikshay.case_utils import CASE_TYPE_TRAIL
from custom.enikshay.expressions import ReferralExpressionBase
from .utils import ENikshayCaseStructureMixin


class ReferralTestExpression(ReferralExpressionBase):
    """
    A version of the ReferralExpressionBase that just returns the referral or trail case for testing purposes

    Other subclasses of ReferralExpressionBase would return a particular case property from the case, but for
    testing purposes it is sufficient to just confirm that the right case is being returned at this step.
    """
    def _handle_referral_case(self, referral):
        return referral


@nottest
def referral_test_expression(spec, context):
    """
    Factory function for ReferralTestExpression
    """
    wrapped = ReferralTestExpression.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.person_id_expression, context)
    )
    return wrapped


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestReferralExpressions(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(TestReferralExpressions, self).setUp()
        self.cases = self.create_case_structure()

    def tearDown(self):
        super(TestReferralExpressions, self).tearDown()
        delete_all_cases()

    def get_referral_expression_case(self, person_id):
        """
        Evaluate the ReferralTestExpression against the given person_id
        """
        context = EvaluationContext({"domain": self.domain})
        expression = referral_test_expression({
            # "domain": self.domain,
            'person_id_expression': {
                "type": "property_name",
                "property_name": "person_id"
            }
        }, context)

        referral_or_trail = expression({"person_id": person_id}, context)
        return referral_or_trail

    def test_person_with_no_referrals(self):
        self.assertIsNone(self.get_referral_expression_case(self.person_id))

    def test_person_with_open_referral(self):
        referral_case_id = uuid.uuid4().hex
        self.create_referral_case(referral_case_id)

        self.assertEqual(
            self.get_referral_expression_case(self.person_id).case_id,
            referral_case_id
        )

    def accept_referral(self, referral_case):
        # Note that the actual app workflow changes additional properties/ownership
        person_case_id = referral_case.indices[0].referenced_id
        self.factory.update_case(person_case_id, update={"awaiting_claim": "no"})
        # Note that actual app workflow reassigns person case as well
        self.factory.update_case(referral_case.case_id, close=True)

        trail = self.factory.create_or_update_case(
            CaseStructure(
                case_id=uuid.uuid4().hex,
                attrs={
                    "case_type": CASE_TYPE_TRAIL,
                    "create": True,
                    "update": {
                        "referral_id": referral_case.case_id
                    }
                },
                indices=[CaseIndex(
                    CaseStructure(case_id=person_case_id, attrs={"create": False}),
                    identifier='host',
                    relationship=CASE_INDEX_CHILD,
                    related_type='person',
                )],
                walk_related=False,
            )
        )[0]
        return trail

    def test_person_with_accepted_referral(self):
        referral_case_id = uuid.uuid4().hex
        referral_case = self.create_referral_case(referral_case_id)[0]
        trail = self.accept_referral(referral_case)

        self.assertEqual(
            self.get_referral_expression_case(self.person_id),
            trail
        )

    def reject_referral(self, referral_case_id):
        # Note that the actual app workflow changes additional properties, including the case owner
        self.factory.update_case(
            referral_case_id,
            update={
                "referral_status": "rejected",
            },
            close=True,
        )

    def test_person_with_rejected_referral(self):
        referral_case_id = uuid.uuid4().hex
        self.create_referral_case(referral_case_id)
        self.reject_referral(referral_case_id)

        self.assertEqual(
            self.get_referral_expression_case(self.person_id),
            None
        )

    def test_person_accepted_then_pending(self):
        referral_1_case_id = uuid.uuid4().hex
        referral_1 = self.create_referral_case(referral_1_case_id)[0]
        self.accept_referral(referral_1)

        referral_2_case_id = uuid.uuid4().hex
        referral_2 = self.create_referral_case(referral_2_case_id)[0]

        self.assertEqual(
            self.get_referral_expression_case(self.person_id),
            referral_2
        )

    def test_person_accepted_then_rejected(self):
        referral_1_case_id = uuid.uuid4().hex
        referral_1 = self.create_referral_case(referral_1_case_id)[0]
        trail = self.accept_referral(referral_1)

        referral_2_case_id = uuid.uuid4().hex
        self.create_referral_case(referral_2_case_id)
        self.reject_referral(referral_2_case_id)

        self.assertEqual(
            self.get_referral_expression_case(self.person_id),
            trail
        )

    def test_person_accepted_twice(self):
        referral_1_case_id = uuid.uuid4().hex
        referral_1 = self.create_referral_case(referral_1_case_id)[0]
        self.accept_referral(referral_1)

        referral_2_case_id = uuid.uuid4().hex
        referral_2 = self.create_referral_case(referral_2_case_id)[0]
        trail_2 = self.accept_referral(referral_2)

        self.assertEqual(
            self.get_referral_expression_case(self.person_id),
            trail_2
        )

    def test_person_rejected_then_pending(self):
        referral_1_case_id = uuid.uuid4().hex
        self.create_referral_case(referral_1_case_id)
        self.reject_referral(referral_1_case_id)

        referral_2_case_id = uuid.uuid4().hex
        referral_2 = self.create_referral_case(referral_2_case_id)[0]

        self.assertEqual(
            self.get_referral_expression_case(self.person_id),
            referral_2
        )

    def test_person_rejected_then_accepted(self):
        referral_1_case_id = uuid.uuid4().hex
        self.create_referral_case(referral_1_case_id)
        self.reject_referral(referral_1_case_id)

        referral_2_case_id = uuid.uuid4().hex
        referral_2 = self.create_referral_case(referral_2_case_id)[0]
        trail = self.accept_referral(referral_2)

        self.assertEqual(
            self.get_referral_expression_case(self.person_id),
            trail
        )


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestEpisodeFromPersonExpression(ENikshayCaseStructureMixin, TestCase):

    def setUp(self):
        super(TestEpisodeFromPersonExpression, self).setUp()
        self.cases = self.create_case_structure()

    def tearDown(self):
        super(TestEpisodeFromPersonExpression, self).tearDown()
        delete_all_cases()

    def test_expression_when_episode_exists(self):
        context = EvaluationContext({"domain": self.domain})
        expression = ExpressionFactory.from_spec({
            "type": "enikshay_episode_from_person",
            "person_id_expression": self.person_id,
        })
        self.assertEqual(expression({}, context), self.cases[self.episode_id].to_json())

    def test_expression_when_episode_does_not_exist(self):
        context = EvaluationContext({"domain": self.domain})
        expression = ExpressionFactory.from_spec({
            "type": "enikshay_episode_from_person",
            "person_id_expression": "some_random_id",
        })
        self.assertEqual(expression({}, context), None)
