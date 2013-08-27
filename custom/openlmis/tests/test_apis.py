from datetime import datetime
import os
from django.test import TestCase
from custom.openlmis.api import get_recent_facilities, Facility, get_facility_programs, FacilityProgramLink


ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

class ApiTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')

    def testParseRecentFacilities(self):
        with open(os.path.join(self.datapath, 'recent_facilities.rss')) as f:
            recent = list(get_recent_facilities(f.read()))

        self.assertEqual(2, len(recent))
        [f1, f2] = recent
        for f in recent:
            self.assertEqual(Facility, type(f))

        # sanity check some stuff back
        self.assertEqual('tag:atomfeed.ict4h.org:c992599f-6d91-4f53-b74d-6bb72c7817ee', f1.rss_meta.id)
        self.assertEqual(datetime.strptime('2013-08-19T11:19:09Z', ISO_FORMAT), f1.rss_meta.updated)
        self.assertEqual('FCcode20130819-044859', f1.code)
        self.assertEqual('FCname20130819-044859', f1.name)
        self.assertEqual('Lvl3 Hospital', f1.metadata['type'])
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
        self.assertEqual(-555.5555, f2.metadata['latitude'])
        self.assertEqual(444.4444, f2.metadata['longitude'])
        self.assertEqual(4545.4545, f2.metadata['altitude'])



    def testParseFacilityPrograms(self):
        programs = get_facility_programs((os.path.join(self.datapath, 'facility_programs.rss')))
        for p in programs:
            self.assertEqual(FacilityProgramLink, type(p))
