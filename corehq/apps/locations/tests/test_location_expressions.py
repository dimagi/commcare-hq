from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext


class TestLocationTypeExpression(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationTypeExpression, cls).setUpClass()
        cls.domain_name = "test-domain"
        cls.domain_obj = create_domain(cls.domain_name)
        cls.location_type = LocationType(
            domain=cls.domain_name,
            name="state",
            code="state",
        )
        cls.location_type.save()

        cls.location = SQLLocation(
            domain="test-domain",
            name="Braavos",
            location_type=cls.location_type
        )
        cls.location.save()
        cls.unique_id = cls.location.location_id

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
        cls.domain_obj.delete()
        super(TestLocationTypeExpression, cls).tearDownClass()

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
        doc = {"_id": self.unique_id}
        self._check_expression(doc, "state")

    def test_bad_domain(self):
        doc = {"_id": self.unique_id}
        self._check_expression(doc, None, domain="wrong-domain")

    def test_bad_doc(self):
        doc = {"no_id": "sdf"}
        self._check_expression(doc, None)

    def test_location_not_found(self):
        doc = {"_id": "non_existent_id"}
        self._check_expression(doc, None)


class TestLocationParentIdExpression(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationParentIdExpression, cls).setUpClass()
        cls.domain = 'test-loc-parent-id'
        cls.domain_obj = create_domain(cls.domain)
        cls.continent_location_type = LocationType(
            domain=cls.domain,
            name="continent",
            code="continent",
        )
        cls.continent_location_type.save()
        cls.kingdom_location_type = LocationType(
            domain=cls.domain,
            name="kingdom",
            code="kingdom",
            parent_type=cls.continent_location_type,
        )
        cls.kingdom_location_type.save()
        cls.city_location_type = LocationType(
            domain=cls.domain,
            name="city",
            code="city",
            parent_type=cls.kingdom_location_type,
        )
        cls.city_location_type.save()

        cls.parent = SQLLocation(
            domain=cls.domain,
            name="Westeros",
            location_type=cls.continent_location_type,
            site_code="westeros",
        )
        cls.parent.save()
        cls.child = SQLLocation(
            domain=cls.domain,
            name="The North",
            location_type=cls.kingdom_location_type,
            parent=cls.parent,
            site_code="the_north",
        )
        cls.child.save()
        cls.grandchild = SQLLocation(
            domain=cls.domain,
            name="Winterfell",
            location_type=cls.city_location_type,
            parent=cls.child,
            site_code="winterfell",
        )
        cls.grandchild.save()

        cls.evaluation_context = EvaluationContext({"domain": cls.domain})
        cls.expression_spec = {
            "type": "location_parent_id",
            "location_id_expression": {
                "type": "property_name",
                "property_name": "location_id",
            }
        }
        cls.expression = ExpressionFactory.from_spec(cls.expression_spec)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestLocationParentIdExpression, cls).tearDownClass()

    def test_location_parent_id(self):
        self.assertEqual(
            self.parent.location_id,
            self.expression({'location_id': self.child.location_id}, self.evaluation_context)
        )
        self.assertEqual(
            self.child.location_id,
            self.expression({'location_id': self.grandchild.location_id}, self.evaluation_context)
        )

    def test_location_parent_missing(self):
        self.assertEqual(
            None,
            self.expression({'location_id': 'bad-id'}, self.evaluation_context)
        )

    def test_location_parent_bad_domain(self):
        self.assertEqual(
            None,
            self.expression({'location_id': self.child.location_id}, EvaluationContext({"domain": 'bad-domain'}))
        )

    def test_location_parents_chained(self):
        expression = ExpressionFactory.from_spec({
            "type": "location_parent_id",
            "location_id_expression": {
                "type": "location_parent_id",
                "location_id_expression": {
                    "type": "property_name",
                    "property_name": "location_id",
                }
            }
        })
        self.assertEqual(
            self.parent.location_id,
            expression({'location_id': self.grandchild.location_id}, self.evaluation_context)
        )
