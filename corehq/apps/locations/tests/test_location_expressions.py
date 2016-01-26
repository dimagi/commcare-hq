import uuid
from django.test import TestCase, SimpleTestCase
from fakecouch import FakeCouchDb
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType, Location
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext


class TestLocationTypeExpression(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain_name = "test-domain"
        cls.domain_obj = create_domain(cls.domain_name)
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
        cls.domain_obj.delete()

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


class TestLocationParentIdExpression(SimpleTestCase):

    def setUp(self):
        # we have to set the fake database before any other calls
        self.domain = 'test-loc-parent-id'
        self.evaluation_context = EvaluationContext({"domain": self.domain})
        self.orig_db = Location.get_db()
        self.database = FakeCouchDb()
        Location.set_db(self.database)
        self.parent = self._make_location(_id=uuid.uuid4().hex)
        self.child = self._make_location(
            _id=uuid.uuid4().hex,
            lineage=[self.parent._id]
        )
        self.grandchild = self._make_location(
            _id=uuid.uuid4().hex,
            lineage=[self.child._id, self.parent._id]
        )
        self.expression_spec = {
            "type": "location_parent_id",
            "location_id_expression": {
                "type": "property_name",
                "property_name": "location_id",
            }
        }
        self.expression = ExpressionFactory.from_spec(self.expression_spec)

    def tearDown(self):
        Location.set_db(self.orig_db)

    def test_location_parent_id(self):
        self.assertEqual(
            self.parent._id,
            self.expression({'location_id': self.child._id}, self.evaluation_context)
        )
        self.assertEqual(
            self.child._id,
            self.expression({'location_id': self.grandchild._id}, self.evaluation_context)
        )

    def test_location_parent_missing(self):
        self.assertEqual(
            None,
            self.expression({'location_id': 'bad-id'}, self.evaluation_context)
        )

    def test_location_parent_bad_domain(self):
        self.assertEqual(
            None,
            self.expression({'location_id': self.child._id}, EvaluationContext({"domain": 'bad-domain'}))
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
            self.parent._id,
            expression({'location_id': self.grandchild._id}, self.evaluation_context)
        )

    def _make_location(self, **kwargs):
        kwargs['domain'] = self.domain
        loc = Location(**kwargs)
        self.database.save_doc(loc.to_json())
        return loc
