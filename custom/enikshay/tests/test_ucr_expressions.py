from django.test import TestCase, override_settings

from corehq.apps.userreports.expressions import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext
from custom.enikshay.tests.utils import ENikshayLocationStructureMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestAncestorLocationExpression(ENikshayLocationStructureMixin, TestCase):

    def test_ancestor_location_exists(self):
        context = EvaluationContext({})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': self.phi.location_id,
            'location_type': "sto",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNotNone(ancestor_location)
        self.assertEqual(
            ancestor_location.get("location_id"),
            self.sto.location_id
        )

    def test_ancestor_location_dne(self):
        context = EvaluationContext({})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': self.phi.location_id,
            'location_type': "nonsense",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNone(ancestor_location)

    def test_location_dne(self):
        context = EvaluationContext({})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': "gibberish",
            'location_type': "sto",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNone(ancestor_location)
