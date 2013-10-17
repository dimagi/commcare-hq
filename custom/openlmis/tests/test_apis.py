from datetime import datetime
import os
from django.test import TestCase
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.commtrack.tests import bootstrap_domain
from corehq.apps.locations.models import Location
from custom.openlmis.api import get_facilities, Facility, get_facility_programs, FacilityProgramLink, get_programs_and_products, Program
from custom.openlmis.commtrack import sync_supply_point_to_openlmis
from custom.openlmis.tests.mock_api import MockOpenLMISEndpoint


ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

class FeedApiTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')

    def testParseRecentFacilities(self):
        with open(os.path.join(self.datapath, 'recent_facilities.rss')) as f:
            recent = list(get_facilities(f.read()))

        self.assertEqual(2, len(recent))
        [f1, f2] = recent
        for f in recent:
            self.assertEqual(Facility, type(f))

        # sanity check some stuff back
        self.assertEqual('tag:atomfeed.ict4h.org:c992599f-6d91-4f53-b74d-6bb72c7817ee', f1.rss_meta.id)
        self.assertEqual(datetime.strptime('2013-08-19T11:19:09Z', ISO_FORMAT), f1.rss_meta.updated)
        self.assertEqual('FCcode20130819-044859', f1.code)
        self.assertEqual('FCname20130819-044859', f1.name)
        self.assertEqual('Lvl3 Hospital', f1.type)
        self.assertEqual(-555.5555, f2.latitude)
        self.assertEqual(444.4444, f2.longitude)
        self.assertEqual('Testing description', f1.metadata['description'])
        self.assertEqual('9711231305', f1.metadata['mainPhone'])
        self.assertEqual('9711231305', f1.metadata['fax'])

        self.assertEqual('tag:atomfeed.ict4h.org:e8f2c9ab-1bf5-4ea5-a4f6-476fecb34625', f2.rss_meta.id)
        self.assertEqual(datetime.strptime('2013-08-26T11:05:57Z', ISO_FORMAT), f2.rss_meta.updated)
        self.assertEqual('facilityf10', f2.code)
        self.assertEqual('facilityf10 Village Dispensary', f2.name)
        self.assertEqual('Address1', f2.metadata['address1'])
        self.assertEqual('Address2', f2.metadata['address2'])
        self.assertEqual('virtualgeozone', f2.metadata['geographicZone'])
        self.assertEqual(100, f2.metadata['catchmentPopulation'])
        self.assertEqual(4545.4545, f2.metadata['altitude'])

    def testParseFacilityPrograms(self):
        programs = get_facility_programs((os.path.join(self.datapath, 'facility_programs.rss')))
        for p in programs:
            self.assertEqual(FacilityProgramLink, type(p))

    def testParseProgramProducts(self):
        with open(os.path.join(self.datapath, 'program_products.rss')) as f:
            recent = list(get_programs_and_products(f.read()))

        [program] = recent
        self.assertEqual(Program, type(program))

        # sanity check some stuff back
        self.assertEqual('HIV', program.code)
        self.assertEqual('HIV', program.name)


class PostApiTest(TestCase):

    def setUp(self):
        self.domain = 'post-api-test'
        bootstrap_domain(self.domain)
        self.api = MockOpenLMISEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')

    def testCreateVirtualFacility(self):
        loc = Location(site_code='1234', name='beavis', domain=self.domain,
                       type='chw')
        loc.save()
        sp = make_supply_point(self.domain, loc)
        self.assertTrue(sync_supply_point_to_openlmis(sp, self.api))
