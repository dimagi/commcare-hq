from django.test import TestCase
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext


class TestLocationTypeExpression(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain_name = "test-domain"
        cls.location_type = LocationType(
            domain=cls.domain_name,
            name="state",
            code="state",
        )
        cls.location_type.save()

        cls.location = SQLLocation(
            id="235566",
            location_id="unique-id",
            domain="test-domain",
            name="Braavos",
            location_type=cls.location_type
        )
        cls.location.save()

        cls.spec = {
            "type": "location_type_name",
            "location_id_expression": {
                "type": "property_name",
                "property_name": "_id"
            }
        }

        cls.expression = ExpressionFactory.from_spec(cls.spec)

    @classmethod
    def tearDownClass(cls):
        cls.location.delete()
        cls.location_type.delete()

    def _check_expression(self, doc, expected, domain=None):
        domain = domain or self.domain_name
        self.assertEqual(
            expected,
            self.expression(
                doc,
                context=EvaluationContext({"domain": domain}, 0)
            )
        )

    def test_location_type_expression(self):
        doc = {"_id": "unique-id"}
        self._check_expression(doc, "state")

    def test_bad_domain(self):
        doc = {"_id": "unique-id"}
        self._check_expression(doc, None, domain="wrong-domain")

    def test_bad_doc(self):
        doc = {"no_id": "sdf"}
        self._check_expression(doc, None)

    def test_location_not_found(self):
        doc = {"_id": "non_existent_id"}
        self._check_expression(doc, None)
