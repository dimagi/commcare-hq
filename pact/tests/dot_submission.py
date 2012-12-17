from datetime import datetime, timedelta
import pdb
import dateutil
import os
from django.test import TestCase
from corehq.apps.domain.models import Domain
from couchforms.models import XFormInstance
from pact.enums import PACT_DOTS_DATA_PROPERTY, PACT_DOMAIN
from pact.reports.dot_calendar import query_observations, obs_for_day, merge_dot_day
from pact.utils import submit_xform

START_DATE = datetime.strptime("2012-11-17", "%Y-%m-%d")
END_DATE = datetime.strptime("2012-12-17", "%Y-%m-%d")
ANCHOR_DATE = datetime.strptime("2012-12-07", "%Y-%m-%d")

CASE_ID = "66a4f2d0e9d5467e34122514c341ed92"
PILLBOX_ID = "a1811d7e-c968-4b63-aea5-6195ce0d8759"
NO_PILLBOX_ID = "83bfe01c-9f96-4e25-a1ad-f8164defa5d1"

class dotsSubmissionTests(TestCase):
    def setUp(self):
        two_weeks = timedelta(days=14)
        self.domain = Domain()
        self.domain.name = PACT_DOMAIN
        self.domain.is_active = True
        self.domain.date_created = datetime.utcnow() - two_weeks
        self.domain.save()

        self.submit_url = '/a/%s/receiver' % self.domain.name

        self.pillbox_form = ""
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'dots_data',
                               '01_pillbox.xml')) as fin:
            self.pillbox_form = fin.read()

        self.no_pillbox_form = ""
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'dots_data',
                               '02_no_pillbox.xml')) as fin:
            self.no_pillbox_form = fin.read()

    def testSignal(self):
        """
        Test to ensure that with a DOT submission the signal works
        """
        submit_xform(self.submit_url, self.domain.name, self.pillbox_form)

        submitted = XFormInstance.get(PILLBOX_ID)
        self.assertTrue(hasattr(submitted, PACT_DOTS_DATA_PROPERTY))


    def testPillboxCheck(self):
        #check to make sure that 0th and nth elements are where they ought to be
        #hit the VIEW to make sure it's there

        #make sure the pact_dots_data signal is working

        #check no pillbox check entries that entries show up, and NOTHING more.

        #labeling checks?

        #ensure signal works
        self.testSignal()
        observations = query_observations(CASE_ID, START_DATE, END_DATE)
        print len(observations)
        td = END_DATE - START_DATE

        def check_obs_props(obs, props):
            pdb.set_trace()
            for k, v in props.items():
                print "check obs: %s: %s" % (k, v)
                if k.endswith("_date"):
                    #datetime check
                    obs_date = getattr(obs, k).date()
                    val_date = dateutil.parser.parse(v).date()
                    self.assertEquals(obs_date, val_date)
                else:
                    self.assertEquals(getattr(obs, k), v)
                print "success\n"

        for d in range(td.days):
            this_day = START_DATE + timedelta(days=d)
            print this_day.strftime("%m/%d/%Y")
            day_submissions = obs_for_day(this_day.date(), observations)
            day_data = merge_dot_day(day_submissions)
            if this_day.date() == START_DATE.date():
                #print day_data
                pdb.set_trace()
                art_first = day_data['ART']['dose_dict'][1][0]
                art_first_check_props = {
                    "encounter_date": "2012-12-07T05:00:00Z",
                    "total_doses": 2,
                    "day_note": "art first noon",
                    "day_index": 20,
                    "note": "",
                    "pact_id": "999999",
                    "provider": "ctsims",
                    "method": "pillbox",
                    "observed_date": "2012-11-17T05:00:00Z",
                    #"day_slot": 1,
                    "completed_date": "2012-12-16T22:00:28Z",
                    "adherence": "partial",
                    "dose_number": 1, #zero indexed
#                    "doc_type": "CObservation",
                    "is_reconciliation": False,
                    "anchor_date": "2012-12-07T05:00:00Z",
                    "created_date": "2012-12-16T21:37:52Z",
                    "is_art": True,
                    "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                    "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                }
                check_obs_props(art_first, art_first_check_props)

                non_art_first_1 = day_data['NONART']['dose_dict'][1][0]
                non_art_first_1_props = {
                    "encounter_date": "2012-12-07T05:00:00Z",
                    "total_doses": 3,
                    "day_note": "non art first evening",
                    "day_index": 20,
                    "note": "",
                    "pact_id": "999999",
                    "provider": "ctsims",
                    "method": "pillbox",
                    "observed_date": "2012-11-17T05:00:00Z",
#                    "day_slot": 2,
                    "completed_date": "2012-12-16T22:00:28Z",
                    "adherence": "partial",
                    "dose_number": 1,
#                    "doc_type": "CObservation",
                    "is_reconciliation": False,
                    "anchor_date": "2012-12-07T05:00:00Z",
                    "created_date": "2012-12-16T21:37:52Z",
                    "is_art": False,
                    "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                    "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                }
                check_obs_props(non_art_first_1, non_art_first_1_props)


                non_art_first_2 = day_data['NONART']['dose_dict'][2][0]
                non_art_first_2_props = {
                    "encounter_date": "2012-12-07T05:00:00Z",
                    "total_doses": 3,
                    "day_note": "non art bedtime first",
                    "day_index": 20,
                    "note": "",
                    "pact_id": "999999",
                    "provider": "ctsims",
                    "method": "pillbox",
                    "observed_date": "2012-11-17T05:00:00Z",
#                    "day_slot": 3,
                    "completed_date": "2012-12-16T22:00:28Z",
                    "adherence": "partial",
                    "dose_number": 2,
#                    "doc_type": "CObservation",
                    "is_reconciliation": False,
                    "anchor_date": "2012-12-07T05:00:00Z",
                    "created_date": "2012-12-16T21:37:52Z",
                    "is_art": False,
                    "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                    "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                }
                check_obs_props(non_art_first_2, non_art_first_2_props)

                if this_day.date() == (ANCHOR_DATE - timedelta(days=1)).date():
                    print "Second to last date"
                print day_data

                if this_day.date() == ANCHOR_DATE.date():
                    print "Anchor date"
                    self.assertEqual(len(day_data['NONART']['dose_dict']), 1)
                    non_art_last = day_data['NONART']['dose_dict'][0][0]
                    non_art_last_props = {
                        "encounter_date": "2012-12-07T05:00:00Z",
                        "total_doses": 3,
                        "day_note": "",
                        "day_index": 0,
                        "note": "Anchor same",
                        "pact_id": "999999",
                        "provider": "ctsims",
                        "method": "direct",
                        "observed_date": "2012-12-07T05:00:00Z",
                        #"day_slot": -1,
                        "completed_date": "2012-12-16T22:00:28Z",
                        "adherence": "partial",
                        "dose_number": 0,
#                        "doc_type": "CObservation",
                        "is_reconciliation": False,
                        "anchor_date": "2012-12-07T05:00:00Z",
                        "created_date": "2012-12-16T21:37:52Z",
                        "is_art": False,
                        "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                        "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                    }
                    check_obs_props(non_art_last, non_art_last_props)

                    non_art_last_noon = day_data['NONART']['dose_dict'][1][0]
                    non_art_last_noon_props = {
                        "encounter_date": "2012-12-07T05:00:00Z",
                        "total_doses": 3,
                        "day_note": "non art noon last",
                        "day_index": 0,
                        "note": "Anchor same",
                        "pact_id": "999999",
                        "provider": "ctsims",
                        "method": "pillbox",
                        "observed_date": "2012-12-07T05:00:00Z",
#                        "day_slot": -1,
                        "completed_date": "2012-12-16T22:00:28Z",
                        "adherence": "partial",
                        "dose_number": 1,
#                        "doc_type": "CObservation",
                        "is_reconciliation": False,
                        "anchor_date": "2012-12-07T05:00:00Z",
                        "created_date": "2012-12-16T21:37:52Z",
                        "is_art": False,
                        "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                        "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                    }

                print day_data


                #            print simplejson.dumps(day_data, indent=4)

                #todo: check reconciliation?
                pass
