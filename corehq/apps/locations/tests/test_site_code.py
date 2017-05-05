#!/usr/bin/env python
# -*- coding: utf-8 -*-

from corehq.apps.commtrack.tests.util import bootstrap_domain
from django.test import TestCase
from corehq.apps.locations.models import Location, LocationType
from corehq.apps.locations.tests.util import delete_all_locations


class SiteCodeTest(TestCase):

    domain = 'test-site-code'

    @classmethod
    def setUpClass(cls):
        super(SiteCodeTest, cls).setUpClass()
        cls.project = bootstrap_domain(cls.domain)
        LocationType(domain=cls.domain, name='type').save()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        delete_all_locations()
        super(SiteCodeTest, cls).tearDownClass()

    def testSimpleName(self):
        location = Location(
            name="Some Location",
            domain=self.domain,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'some_location')

    def testOtherCharacters(self):
        location = Location(
            name=u"Somé$ #Location (Old)",
            domain=self.domain,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'some_location_old')

    def testDoesntDuplicate(self):
        location = Location(
            name="Location",
            domain=self.domain,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'location')

        location = Location(
            name="Location",
            domain=self.domain,
            location_type="type"
        )

        location.save()

        self.assertEqual(location.site_code, 'location1')
