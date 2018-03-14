from __future__ import absolute_import
from __future__ import unicode_literals
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


class LocationHierarchyTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LocationHierarchyTest, cls).setUpClass()
        domain = "a-song-of-ice-and-fire"
        domain_obj = create_domain(domain)
        continent_location_type = LocationType(
            domain=domain,
            name="continent",
            code="continent",
        )
        continent_location_type.save()
        kingdom_location_type = LocationType(
            domain=domain,
            name="kingdom",
            code="kingdom",
            parent_type=continent_location_type,
        )
        kingdom_location_type.save()
        city_location_type = LocationType(
            domain=domain,
            name="city",
            code="city",
            parent_type=kingdom_location_type,
        )
        city_location_type.save()

        continent = SQLLocation(
            domain=domain,
            name="Westeros",
            location_type=continent_location_type,
            site_code="westeros",
        )
        continent.save()
        kingdom = SQLLocation(
            domain=domain,
            name="The North",
            location_type=kingdom_location_type,
            parent=continent,
            site_code="the_north",
        )
        kingdom.save()
        city = SQLLocation(
            domain=domain,
            name="Winterfell",
            location_type=city_location_type,
            parent=kingdom,
            site_code="winterfell",
        )
        city.save()

        cls.domain_obj = domain_obj
        cls.domain = domain
        cls.continent = continent
        cls.kingdom = kingdom
        cls.city = city

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(LocationHierarchyTest, cls).tearDownClass()


class TestLocationParentIdExpression(LocationHierarchyTest):

    @classmethod
    def setUpClass(cls):
        super(TestLocationParentIdExpression, cls).setUpClass()
        cls.evaluation_context = EvaluationContext({"domain": cls.domain})
        cls.expression_spec = {
            "type": "location_parent_id",
            "location_id_expression": {
                "type": "property_name",
                "property_name": "location_id",
            }
        }
        cls.expression = ExpressionFactory.from_spec(cls.expression_spec)

    def test_location_parent_id(self):
        self.assertEqual(
            self.continent.location_id,
            self.expression({'location_id': self.kingdom.location_id}, self.evaluation_context)
        )
        self.assertEqual(
            self.kingdom.location_id,
            self.expression({'location_id': self.city.location_id}, self.evaluation_context)
        )

    def test_location_parent_missing(self):
        self.assertEqual(
            None,
            self.expression({'location_id': 'bad-id'}, self.evaluation_context)
        )

    def test_location_parent_bad_domain(self):
        self.assertEqual(
            None,
            self.expression({'location_id': self.kingdom.location_id}, EvaluationContext({"domain": 'bad-domain'}))
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
            self.continent.location_id,
            expression({'location_id': self.city.location_id}, self.evaluation_context)
        )


class TestAncestorLocationExpression(LocationHierarchyTest):

    def test_ancestor_location_exists(self):
        context = EvaluationContext({'domain': self.domain})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': self.city.location_id,
            'location_type': "continent",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNotNone(ancestor_location)
        self.assertEqual(
            ancestor_location.get("location_id"),
            self.continent.location_id
        )

    def test_ancestor_location_dne(self):
        context = EvaluationContext({'domain': self.domain})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': self.kingdom.location_id,
            'location_type': "nonsense",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNone(ancestor_location)

    def test_location_dne(self):
        context = EvaluationContext({'domain': self.domain})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': "gibberish",
            'location_type': "kingdom",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNone(ancestor_location)
