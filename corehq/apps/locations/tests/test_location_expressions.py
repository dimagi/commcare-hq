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


def setup_module():
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

    parent = SQLLocation(
        domain=domain,
        name="Westeros",
        location_type=continent_location_type,
        site_code="westeros",
    )
    parent.save()
    child = SQLLocation(
        domain=domain,
        name="The North",
        location_type=kingdom_location_type,
        parent=parent,
        site_code="the_north",
    )
    child.save()
    grandchild = SQLLocation(
        domain=domain,
        name="Winterfell",
        location_type=city_location_type,
        parent=child,
        site_code="winterfell",
    )
    grandchild.save()

    globals()["domain_obj"] = domain_obj
    globals()["domain"] = domain
    globals()["parent"] = parent
    globals()["child"] = child
    globals()["grandchild"] = grandchild


def teardown_module():
    domain_obj.delete()


class TestLocationParentIdExpression(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationParentIdExpression, cls).setUpClass()
        cls.evaluation_context = EvaluationContext({"domain": domain})
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
            parent.location_id,
            self.expression({'location_id': child.location_id}, self.evaluation_context)
        )
        self.assertEqual(
            child.location_id,
            self.expression({'location_id': grandchild.location_id}, self.evaluation_context)
        )

    def test_location_parent_missing(self):
        self.assertEqual(
            None,
            self.expression({'location_id': 'bad-id'}, self.evaluation_context)
        )

    def test_location_parent_bad_domain(self):
        self.assertEqual(
            None,
            self.expression({'location_id': child.location_id}, EvaluationContext({"domain": 'bad-domain'}))
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
            parent.location_id,
            expression({'location_id': grandchild.location_id}, self.evaluation_context)
        )


class TestAncestorLocationExpression(TestCase):

    def test_ancestor_location_exists(self):
        context = EvaluationContext({})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': grandchild.location_id,
            'location_type': "continent",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNotNone(ancestor_location)
        self.assertEqual(
            ancestor_location.get("location_id"),
            parent.location_id
        )

    def test_ancestor_location_dne(self):
        context = EvaluationContext({})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': child.location_id,
            'location_type': "nonsense",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNone(ancestor_location)

    def test_location_dne(self):
        context = EvaluationContext({})
        expression = ExpressionFactory.from_spec({
            'type': 'ancestor_location',
            'location_id': "gibberish",
            'location_type': "kingdom",
        }, context)

        ancestor_location = expression({}, context)
        self.assertIsNone(ancestor_location)
