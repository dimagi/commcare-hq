import time
import pdb
import dateutil
import os
from django.test import TestCase
import ipdb
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
from pact.dot_data import filter_obs_for_day, query_observations, DOTDay, get_dots_case_json
from pact.enums import PACT_DOTS_DATA_PROPERTY, PACT_DOMAIN, XMLNS_DOTS_FORM, XMLNS_PATIENT_UPDATE_DOT, DOT_DAYS_INTERVAL, DOT_NONART, DOT_ART, DOT_ART_IDX, DOT_NONART_IDX
from pact.models import PactPatientCase
from pact.regimen import regimen_dict_from_choice
from pact.utils import submit_xform
from datetime import datetime, timedelta


START_DATE = datetime.utcnow() - timedelta(days=7)
END_DATE = datetime.utcnow()

#ANCHOR_DATE_A_STR = '2013-06-25'
ANCHOR_DATE_A = datetime.utcnow() - timedelta(days=1)
#ANCHOR_DATE_B_STR = '2013-06-26'
#ANCHOR_DATE_B = datetime.strptime(ANCHOR_DATE_B_STR, "%Y-%m-%d")
ANCHOR_DATE_B = datetime.utcnow() - timedelta(days=0)

CASE_ID = "b975804a513743738a216246a293e819"

FORM_A = "a672ffc855c44f29906b0a9913f07cc7"
FORM_B = "4ed0045c580d415985c15f09282b4a22"
CTSIMS_ID = 'ff6c662bfc2a448dadc9084056a4abdf'


class dotsOrderingTests(TestCase):
    def setUp(self):
        for doc in XFormInstance.get_db().view('couchforms/by_xmlns', reduce=False,
                                               include_docs=True).all():
            #purge all xforms prior to start
            if doc['doc']['xmlns'] in [XMLNS_DOTS_FORM, XMLNS_PATIENT_UPDATE_DOT]:
                XFormInstance.get_db().delete_doc(doc['doc'])

        two_weeks = timedelta(days=14)
        self.domain = Domain.get_or_create_with_name(PACT_DOMAIN, is_active=True)
        self.domain.date_created = datetime.utcnow() - two_weeks
        self.domain.save()

        self.submit_url = '/a/%s/receiver' % self.domain.name

        self.user = CommCareUser.create(self.domain.name, 'ctsims', 'mockmock', uuid=CTSIMS_ID)

        nonart_case_regimens = regimen_dict_from_choice(DOT_NONART, "morning,bedtime")
        art_case_regimens = regimen_dict_from_choice(DOT_ART, "morning,bedtime")
        props = {'_id': CASE_ID, 'dot_status': 'DOT1', 'domain': self.domain.name}
        props.update(nonart_case_regimens)
        props.update(art_case_regimens)

        self.case = CommCareCase(**props)
        self.case.save()

        self.form_a = ""
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'dots_data',
                               '05_uncheck_a.xml')) as fin:
            self.form_a = fin.read() % {
                'encounter_date': ANCHOR_DATE_A.strftime('%Y-%m-%d'),
                'anchor_date': ANCHOR_DATE_A.strftime("%d %b %Y")
            }

        self.form_b = ""
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'dots_data',
                               '06_uncheck_b.xml')) as fin:
            self.form_b = fin.read() % {
                'encounter_date': ANCHOR_DATE_B.strftime('%Y-%m-%d'),
                'anchor_date': ANCHOR_DATE_B.strftime("%d %b %Y")
            }



    def tearDown(self):
        CommCareCase.get_db().delete_doc(CASE_ID)
        CommCareUser.get_db().delete_doc(CTSIMS_ID)
        self.user = None

    def testFormA(self):
        """
        Test the dot map function that the no-pillbox checker is faithfully returning DOT data in the calendar thanks to the view
        """
        bundle = {
            "xml": self.form_a,
            "start_date": START_DATE,
            "end_date": ANCHOR_DATE_A,
            "xform_id": FORM_A,
            "anchor_date": ANCHOR_DATE_A,
            'nonart': [["full", "pillbox", "", 0], ["unchecked", "pillbox", "", 3]],
            'art': [["full", "self", "", 0], ["unchecked", "pillbox", "", 3]],
            'submit_idx': -1,
            'check_idx': -2,
        }
        print "######### TestFormA"
        print self.form_a
        self._submitAndVerifyBundle(bundle)

        print "######### END TestFormA"

    def testFormB(self, verify=True):
        bundle = {
            "xml": self.form_b,
            "start_date": START_DATE,
            "end_date": ANCHOR_DATE_B,
            "xform_id": FORM_B,
            "anchor_date": ANCHOR_DATE_B,
            'nonart': [["unchecked", "pillbox", "", 0], ["empty", "pillbox", "", 3]],
            'art': [["unchecked", "pillbox", "", 0], ["empty", "pillbox", "", 3]],
            'submit_idx': -2,
            'check_idx': -2
        }
        print "######### TestFormB"
        self._submitAndVerifyBundle(bundle, verify=verify)
        print "######### END TestFormB"

    def testForA_B(self):

        print "######### TestFormAB"
        self.testFormA()
        self.testFormB(verify=False)

        updated_case = PactPatientCase.get(CASE_ID)
        case_dots = updated_case.dots
        days = simplejson.loads(case_dots)['days']

        nonart = [["full", "pillbox", "", 0], ["empty", "pillbox", "", 3]]
        art = [["full", "self", "", 0], ["empty", "pillbox", "", 3]]

        examine_day = days[-2]

        self._verify_dot_cells(nonart, art, examine_day)
        print "######### END TestFormAB"

    def _submitAndVerifyBundle(self, bundle, verify=True):
        start_nums = len(self.case.xform_ids)
        submit_xform(self.submit_url, self.domain.name, bundle['xml'])
        time.sleep(1)
        #ipdb.set_trace()
        submitted = XFormInstance.get(bundle['xform_id'])
        self.assertTrue(hasattr(submitted, PACT_DOTS_DATA_PROPERTY))

        submitted_dots = getattr(submitted, PACT_DOTS_DATA_PROPERTY)
        updated_case = PactPatientCase.get(CASE_ID)
        #case_json = get_dots_case_json(PactPatientCase.get(CASE_ID), anchor_date=bundle['anchor_date'])
        #self.assertEqual(start_nums + 2, len(updated_case.xform_ids))
        case_dots = get_dots_case_json(updated_case)
        days = case_dots['days']

        print "anchor: %s" % bundle['anchor_date']
        print 'form data: %s' % submitted_dots['dots']['days'][bundle['submit_idx']]
        #print "Case data: %s" % days[bundle['day_idx']]
        print "Case data -1: %s" % days[-1]
        print "Case data -2: %s" % days[-2]
        print "Case data checker: %s" % days[bundle['check_idx']]

        if verify:
            nonart_submissions = bundle['nonart']
            art_submissions = bundle['art']
            examine_day = days[bundle['check_idx']]

            print "compare nonart: %s" % nonart_submissions
            print "compare art: %s" % art_submissions

            self._verify_dot_cells(nonart_submissions, art_submissions, examine_day)


    def _verify_dot_cells(self, nonart_submissions, art_submissions, examine_day):
        for day_dose_idx, time_string in enumerate(['morning', 'evening']):
            self.assertEqual(examine_day[DOT_NONART_IDX][day_dose_idx][0:2], nonart_submissions[day_dose_idx][0:2])
            self.assertEqual(examine_day[DOT_ART_IDX][day_dose_idx][0:2], art_submissions[day_dose_idx][0:2])

