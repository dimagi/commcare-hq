#!/usr/bin/env python
# -*- coding: utf-8 -*-

from corehq.apps.commtrack.tests.util import bootstrap_domain
from django.test import TestCase
from corehq.apps.locations.models import Location, LocationType


class SiteCodeTest(TestCase):

    def setUp(self):
        self.domain = bootstrap_domain()
        LocationType(domain=self.domain.name, name='type').save()

    def testSimpleName(self):
        location = Location(
            name="Some Location",
            domain=self.domain.name,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'some_location')

    def testOtherCharacters(self):
        location = Location(
            name=u"Somé$ #Location (Old)",
            domain=self.domain.name,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'some_location_old')

    def testDoesntDuplicate(self):
        location = Location(
            name="Location",
            domain=self.domain.name,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'location')

        location = Location(
            name="Location",
            domain=self.domain.name,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'location1')
