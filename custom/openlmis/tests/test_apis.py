from datetime import datetime
import json
import os
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.locations.models import Location, LocationType
from custom.openlmis.api import get_facilities, Facility, get_facility_programs, FacilityProgramLink, get_programs_and_products, Program, RequisitionDetails, RequisitionStatus, get_requisition_statuses, Requisition
from custom.openlmis.commtrack import sync_supply_point_to_openlmis, submit_requisition
from custom.openlmis.tests.mock_api import MockOpenLMISEndpoint


ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
TEST_DOMAIN_API = "commtrack-api-test"

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

    def testParseProgramJson(self):
        with open(os.path.join(self.datapath, 'sample_program.json')) as f:
            program = Program.from_json(json.loads(f.read()))

        self.assertEqual('ESS_MEDS', program.code)
        self.assertEqual('ESSENTIAL MEDICINES', program.name)
        self.assertEqual(35, len(program.products))
        p = program.products[0]
        self.assertEqual('P75', p.code)
        self.assertEqual('Malaria Rapid Diagnostics Tests', p.name)
        self.assertEqual('P75', p.code)
        self.assertEqual('TDF/FTC/EFV', p.description)
        self.assertEqual(10, p.unit)
        self.assertEqual('Analgesics', p.category)

    def testParseRequisitionDetailsJson(self):
        with open(os.path.join(self.datapath, 'sample_requisition_details.json')) as f:
            requisition = RequisitionDetails.from_json(json.loads(f.read()))

        self.assertEqual(1, requisition.id)
        self.assertEqual("HIV", requisition.program_id)
        self.assertEqual("F10", requisition.agent_code)
        self.assertEqual(False, requisition.emergency)
        self.assertEqual(1358274600000, requisition.period_start_date)
        self.assertEqual(1359570599000, requisition.period_end_date)

        self.assertEqual(1, len(requisition.products))

        self.assertEqual("P10", requisition.products[0].code)
        self.assertEqual(3, requisition.products[0].beginning_balance)
        self.assertEqual(0, requisition.products[0].quantity_received)
        self.assertEqual(1, requisition.products[0].quantity_dispensed)
        self.assertEqual(-2, requisition.products[0].total_losses_and_adjustments)
        self.assertEqual(0, requisition.products[0].stock_in_hand)
        self.assertEqual(2, requisition.products[0].new_patient_count)
        self.assertEqual(2, requisition.products[0].stock_out_days)
        self.assertEqual(3, requisition.products[0].quantity_requested)
        self.assertEqual("reason", requisition.products[0].reason_for_requested_quantity)
        self.assertEqual(57, requisition.products[0].calculated_order_quantity)
        self.assertEqual(65, requisition.products[0].quantity_approved)
        self.assertEqual("1", requisition.products[0].remarks)

        self.assertEqual("RELEASED", requisition.requisition_status)
        self.assertEqual(1, requisition.order_id)
        self.assertEqual("RELEASED", requisition.order_status)
        self.assertEqual("F10", requisition.supplying_facility_code)


    def testParseRequisitionStatus(self):
        with open(os.path.join(self.datapath, 'requisition_status_feed.rss')) as f:
            recent = list(get_requisition_statuses(f.read()))

        [r1, r2] = recent
        self.assertEqual(2, len(recent))
        for f in recent:
            self.assertEqual(RequisitionStatus, type(f))


        #Sanity CheckList for two events
        self.assertEqual('tag:atomfeed.ict4h.org:f4fa4edf-60be-4b4b-abfc-624a0d32f3ca', r1.rss_meta.id)
        self.assertEqual(datetime.strptime('2013-10-29T10:11:49Z', ISO_FORMAT), r1.rss_meta.updated)
        self.assertEqual(28, r1.requisition_id)
        self.assertEqual('INITIATED', r1.requisition_status)
        self.assertFalse(r1.emergency)
        self.assertIsNone(r1.order_id)
        self.assertIsNone(r1.order_status)
        self.assertEqual(1358274600000, r1.start_date)
        self.assertEqual(1359570599000, r1.end_date)

        self.assertEqual('tag:atomfeed.ict4h.org:6364418f-91dc-42d6-a108-36ef39e383c0', r2.rss_meta.id)
        self.assertEqual(datetime.strptime('2013-10-29T10:11:50Z', ISO_FORMAT), r2.rss_meta.updated)
        self.assertEqual(28, r2.requisition_id)
        self.assertEqual('RELEASED', r2.requisition_status)
        self.assertFalse(r1.emergency)
        self.assertEqual(28, r2.order_id)
        self.assertEqual('RECEIVED', r2.order_status)
        self.assertEqual(1358274600000, r2.start_date)
        self.assertEqual(1359570599000, r2.end_date)


class PostApiTest(TestCase):

    def setUp(self):
        self.domain = 'post-api-test'
        bootstrap_domain(self.domain)
        self.api = MockOpenLMISEndpoint("uri://mock/lmis/endpoint", username='ned', password='honor')
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        LocationType.objects.get_or_create(domain=self.domain, name='chw')

    def testCreateVirtualFacility(self):
        loc = Location(site_code='1234', name='beavis', domain=self.domain,
                       location_type='chw')
        loc.save()
        sp = loc.linked_supply_point()
        self.assertTrue(sync_supply_point_to_openlmis(sp, self.api))
        self.assertTrue(sync_supply_point_to_openlmis(sp, self.api, False))

    def testSubmitRequisition(self):
        with open(os.path.join(self.datapath, 'sample_requisition_data.json')) as f:
            requisition = Requisition.from_json(json.loads(f.read()))
        self.assertTrue(submit_requisition(requisition, self.api))
