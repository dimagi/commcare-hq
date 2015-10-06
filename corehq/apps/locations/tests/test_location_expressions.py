from django.test import TestCase
from corehq.apps.locations.models import SQLLocation, LocationType


class TestLocationTypeExpression(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.location_type = LocationType(
            domain="domain",
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
            "type": "expression",
            "expression": {
              "type": "location_type_name"
            },
            "datatype": "string",
            "column_id": "col"
        }
        from corehq.apps.userreports.indicators.factory import IndicatorFactory

        cls.indicator = IndicatorFactory.from_spec(cls.spec)

    @classmethod
    def tearDownClass(cls):
        cls.location.delete()
        cls.location_type.delete()

    def testSpec(self):
        doc = {"_id": "unique-id"}
        [result] = self.indicator.get_values(doc)

        self.assertEqual("state", result.value)

    def test_bad_doc(self):
        doc = {"no_id": "sdf"}
        [result] = self.indicator.get_values(doc)

        self.assertEqual(None, result.value)

    def test_location_not_found(self):
        doc = {"_id": "non_existent_id"}
        [result] = self.indicator.get_values(doc)

        self.assertEqual(None, result.value)
