from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import LocationXpathValidationError
from corehq.apps.app_manager.xpath import LocationXpath


class LocationXpathTest(SimpleTestCase):

    def setUp(self):
        self.hierarchy = {
            None: ["state"],
            "state": ["district"],
            "district": ["block"],
            "block": ["outlet"],
        }

    def testValidXpathExpressions(self):
        test_cases = [
            ("outlet:outlet/location_type", "instance('commtrack:locations')/states/state/districts/district/blocks/block/outlets/outlet[@id = current()/location_id]/location_type"),
            ("outlet:block/name", "instance('commtrack:locations')/states/state/districts/district/blocks/block[count(outlets/outlet[@id = current()/location_id]) > 0]/name"),
            ("outlet:district/name", "instance('commtrack:locations')/states/state/districts/district[count(blocks/block/outlets/outlet[@id = current()/location_id]) > 0]/name"),
            ("district:district/location_type", "instance('commtrack:locations')/states/state/districts/district[@id = current()/location_id]/location_type"),
            ("district:state/name", "instance('commtrack:locations')/states/state[count(districts/district[@id = current()/location_id]) > 0]/name"),
        ]
        for input, expected in test_cases:
            self.assertEqual(expected, LocationXpath('commtrack:locations').location(input, self.hierarchy))

    def testFormatErrorCases(self):
        test_cases = [
            'badformatalloneword',
            'badformat:noslash',
            'badformat/nocolon'
            'badformat:too:many/colons'
            'badformat:too/many/slashes'
        ]
        for input in test_cases:
            self.assertRaises(
                LocationXpathValidationError,
                LocationXpath('commtrack:locations').validate,
                input, self.hierarchy,
            )
            self.assertRaises(
                LocationXpathValidationError,
                LocationXpath('commtrack:locations').location,
                input, self.hierarchy,
            )

    def testStructureErrorCases(self):
        test_cases = [
            'unknowntype:outlet/location_type',
            'outlet:unknowntype/location_type',
            'state:outlet/location_type',  # can only point to parents
        ]
        for input in test_cases:
            self.assertRaises(
                LocationXpathValidationError,
                LocationXpath('commtrack:locations').validate,
                input, self.hierarchy,
            )
            self.assertRaises(
                LocationXpathValidationError,
                LocationXpath('commtrack:locations').location,
                input, self.hierarchy,
            )
