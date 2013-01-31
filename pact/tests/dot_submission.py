from datetime import datetime, timedelta
import pdb
import dateutil
import os
from django.test import TestCase
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
from pact.dot_data import filter_obs_for_day, query_observations, DOTDay, get_dots_case_json
from pact.enums import PACT_DOTS_DATA_PROPERTY, PACT_DOMAIN, XMLNS_DOTS_FORM, XMLNS_PATIENT_UPDATE_DOT, DOT_DAYS_INTERVAL, DOT_NONART, DOT_ART
from pact.models import PactPatientCase
from pact.regimen import regimen_dict_from_choice
from pact.utils import submit_xform

NO_PILLBOX_ID = "83bfe01c-9f96-4e25-a1ad-f8164defa5d1"
START_DATE = datetime.strptime("2012-11-17", "%Y-%m-%d")
END_DATE = datetime.strptime("2012-12-17", "%Y-%m-%d")
ANCHOR_DATE = datetime.strptime("2012-12-07", "%Y-%m-%d")
#ANCHOR_DATE = datetime.strptime("7 Dec 2012 05:00:00 GMT", "%d %b %Y ")

CASE_ID = "66a4f2d0e9d5467e34122514c341ed92"
PILLBOX_ID = "a1811d7e-c968-4b63-aea5-6195ce0d8759"

NO_PILLBOX_ID2 = "ea30a77d-389c-4743-b9ae-16e0bdf057de"
START_DATE2 = datetime.strptime("2013-01-01", "%Y-%m-%d")
END_DATE2 = datetime.strptime("2013-1-30", "%Y-%m-%d")
ANCHOR_DATE2 = datetime.strptime("2013-1-22", "%Y-%m-%d")

CTSIMS_ID = 'ff6c662bfc2a448dadc9084056a4abdf'

class dotsSubmissionTests(TestCase):
    def setUp(self):
        two_weeks = timedelta(days=14)
        self.domain = Domain()
        self.domain.name = PACT_DOMAIN
        self.domain.is_active = True
        self.domain.date_created = datetime.utcnow() - two_weeks
        self.domain.save()

        self.submit_url = '/a/%s/receiver' % self.domain.name

        self.user = CommCareUser.create(self.domain.name, 'ctsims', 'mockmock', uuid=CTSIMS_ID)

        nonart_case_regimens = regimen_dict_from_choice(DOT_NONART, "morning,evening,bedtime")
        art_case_regimens = regimen_dict_from_choice(DOT_ART, "morning,noon")
        props= {'_id': CASE_ID}
        props.update(nonart_case_regimens)
        props.update(art_case_regimens)
        case = CommCareCase(**props)
        case.save()

        #generate CaseDoc

        self.pillbox_form = ""
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'dots_data',
                               '01_pillbox.xml')) as fin:
            self.pillbox_form = fin.read()

        self.no_pillbox_form = ""
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'dots_data',
                               '02_no_pillbox.xml')) as fin:
            self.no_pillbox_form = fin.read()
        self.no_pillbox_form2 = ""
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'dots_data',
                               '03_no_pillbox.xml')) as fin:
            self.no_pillbox_form2 = fin.read()


    def tearDown(self):
        for doc in XFormInstance.get_db().view('couchforms/by_xmlns', reduce=False, include_docs=True).all():
            XFormInstance.get_db().delete_doc(doc['doc'])
        CommCareCase.get_db().delete_doc(CASE_ID)
        self.user.delete()


    def testSignal(self):
        """
        Test to ensure that with a DOT submission the signal works
        """
        start_count = len(XFormInstance.view('couchforms/by_xmlns', reduce=False).all())

        submit_xform(self.submit_url, self.domain.name, self.pillbox_form)
        submitted = XFormInstance.get(PILLBOX_ID)
        self.assertTrue(hasattr(submitted, PACT_DOTS_DATA_PROPERTY))

        dot_count = XFormInstance.view('couchforms/by_xmlns', key=XMLNS_DOTS_FORM).all()[0]['value']
        update_count = XFormInstance.view('couchforms/by_xmlns', key=XMLNS_PATIENT_UPDATE_DOT).all()[0]['value']

        self.assertEquals(dot_count, update_count)
        self.assertEquals(start_count + 2, dot_count + update_count)

        casedoc = CommCareCase.get(CASE_ID)
        self.assertEqual(casedoc.xform_ids[-2], PILLBOX_ID)
        computed_submit = XFormInstance.get(casedoc.xform_ids[-1])
        self.assertEqual(computed_submit.xmlns, XMLNS_PATIENT_UPDATE_DOT)


    def testNoPillboxCheckFirst(self):
        """
        Test the dot map function that the no-pillbox checker is faithfully returning DOT data in the calendar thanks to the view
        """
        bundle = {"xml": self.no_pillbox_form, "start_date": START_DATE, "end_date": END_DATE, "xform_id": NO_PILLBOX_ID, "anchor_date": END_DATE}
        self._doTestNoPillbox(bundle)

    def testNoPillboxCheckSecond(self):
        bundle = {"xml": self.no_pillbox_form2, "start_date": START_DATE2, "end_date": END_DATE2, "xform_id": NO_PILLBOX_ID2, "anchor_date": END_DATE2}
        self._doTestNoPillbox(bundle)

    def _doTestNoPillbox(self, bundle):
        submit_xform(self.submit_url, self.domain.name, bundle['xml'])
        submitted = XFormInstance.get(bundle['xform_id'])
        self.assertTrue(hasattr(submitted, PACT_DOTS_DATA_PROPERTY))
        observations = query_observations(CASE_ID, bundle['start_date'], bundle['end_date'])
        observed_dates = set()
        #assume to be five - 3,2 same as the regimen count, we are refilling empties
        self.assertEqual(5, len(observations), msg="Observations do not match regimen count: %d != %d" % ( 5, len(observations)))
        art_nonart = set()
        for obs in observations:
            observed_dates.add(obs.observed_date)
            self.assertEquals(obs.day_note, "No check, from form") #magic string from the view to indicate a generated DOT observation from form data.
            art_nonart.add(obs.is_art)
            self.assertEquals(obs.doc_id, bundle['xform_id'])
            print obs.to_json()

        art = filter(lambda x: x.is_art, observations)
        self.assertEquals(2, len(art))
        art_answered = filter(lambda x: x.adherence != "unchecked", art)
        self.assertEquals(1, len(art_answered))

        nonart = filter(lambda x: not x.is_art, observations)
        self.assertEquals(3, len(nonart))
        nonart_answered = filter(lambda x: x.adherence != "unchecked", nonart)
        self.assertEquals(1, len(nonart_answered))

        #this only does SINGLE observations for art and non art
        self.assertEquals(len(observed_dates), 1)
        self.assertEquals(len(art_nonart), 2)
        # inspect the regenerated submission and ensure the built xml block is correctly filled.

        case_json = get_dots_case_json(PactPatientCase.get(CASE_ID), anchor_date=bundle['anchor_date'])
        enddate = bundle['anchor_date'] # anchor date of this submission
        #encounter_date = datetime.strptime(submitted.form['encounter_date'], '%Y-%m-%d')
        encounter_date = submitted.form['encounter_date']

        #print simplejson.dumps(case_json, indent=4)
        for day_delta in range(DOT_DAYS_INTERVAL):
            obs_date = enddate - timedelta(days=day_delta)
            ret_index = DOT_DAYS_INTERVAL - day_delta -1

            print obs_date.strftime("%Y-%m-%d")

            day_arr = case_json['days'][ret_index]
            nonart_day_data = day_arr[0]
            art_day_data = day_arr[1]

            if obs_date.date() == encounter_date:
                print "\tespecially no pillbox check days"
                print nonart_day_data
                print art_day_data

            self.assertEquals(len(nonart_day_data), 3)
            self.assertEquals(len(art_day_data), 2)
            print "\tsuccess"




            #day_data = DOTDay.merge_from_observations(day_arr)
            #ret['days'].append(day_data.to_case_json(casedoc))




    def testDOTFormatConversion(self):
        """
        When a DOT submission comes in, it gets sliced into the CObservations
        and put into the DOTDay format.

        On resubmit/recompute, it's transmitted back into the packed json format and sent back to the phone and resubmitted with new data.
        This test confirms that the conversion process works.
        """
        self.testSignal()

        submitted = XFormInstance.get(PILLBOX_ID)
        orig_data = getattr(submitted, PACT_DOTS_DATA_PROPERTY)['dots']
        orig_anchor = orig_data['anchor']
        del orig_data['anchor'] # can't reproduce gmt offset

        observations = query_observations(CASE_ID, START_DATE, END_DATE)

        #hack, bootstrap the labels manually
        nonart_idx = [0, 2, 3]
        art_idx = [0, 1]
        casedoc = PactPatientCase.get(CASE_ID)
        casedoc.nonartregimen = 3
        casedoc.dot_n_one = 0
        casedoc.dot_n_two = 2
        casedoc.dot_n_three = 3
        casedoc.dot_n_four = None

        casedoc.artregimen = 2
        casedoc.dot_a_one = 0
        casedoc.dot_a_two = 1
        casedoc.dot_a_three = ''
        casedoc.dot_a_four = None

        computed_json = simplejson.loads(
            simplejson.dumps(get_dots_case_json(casedoc, anchor_date=ANCHOR_DATE)))
        computed_anchor = computed_json['anchor']
        del computed_json['anchor']

        for k in orig_data.keys():
            if k != 'days':
            #                print "%s:\n\t%s\n\t%s" % (k, orig_data[k], computed_json[k])
                self.assertEquals(orig_data[k], computed_json[k])
            #            else:
            #                print '### Days ###"'
            #                for x in range(DOT_DAYS_INTERVAL):
            #                    obs_date = ANCHOR_DATE + timedelta(days=x)-timedelta(days=DOT_DAYS_INTERVAL)
            #                    print "%d: %s" % (x, obs_date.strftime("%m/%d/%Y"))
            #                    print "\to: %s\n\tc: %s\n" % (orig_data['days'][x], computed_json['days'][x])
            ##                    print filter_obs_for_day(obs_date.date(), observations)

        self.assertEquals(simplejson.dumps(orig_data), simplejson.dumps(computed_json))


    def testPillboxCheck(self):
        """
        This test tries to accomplish a few things
        0: ensure the content of the signal is correctly set
        1: verify that the dots_observations view is working correctly in reporting dates correclty back in order
        2: Ensure that if you fill out the questions on the form, it won't redundantly fill out the pillbox cells again as well
        3: ensure that proper ART/NonART sequences are put in the correct buckets when combined into a "DOTS Day" cell

        todo: get label day_slot to work correctly
        """
        #check to make sure that 0th and nth elements are where they ought to be
        #hit the VIEW to make sure it's there
        #make sure the pact_dots_data signal is working
        #check no pillbox check entries that entries show up, and NOTHING more.
        #ensure signal works
        #todo: labeling checks

        self.testSignal()
        observations = query_observations(CASE_ID, START_DATE, END_DATE)
        td = END_DATE - START_DATE

        def check_obs_props(obs, props):
            for k, v in props.items():
                if k.endswith("_date"):
                    #datetime check
                    obs_date = getattr(obs, k).date()
                    val_date = dateutil.parser.parse(v).date()
                    self.assertEquals(obs_date, val_date)
                else:
                    self.assertEquals(getattr(obs, k), v,
                                      msg="Error, observation %s\n\t%s didn't match: %s != %s" % (
                                      simplejson.dumps(obs.to_json(), indent=4), k, getattr(obs, k),
                                      v))

        for d in range(td.days):
            this_day = START_DATE + timedelta(days=d)
            day_submissions = filter_obs_for_day(this_day.date(), observations)
            day_data = DOTDay.merge_from_observations(day_submissions)
            if this_day.date() == START_DATE.date():
                art_first = day_data.art.dose_dict[1][0]
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

                non_art_first_1 = day_data.nonart.dose_dict[1][0]
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

                non_art_first_2 = day_data.nonart.dose_dict[2][0]
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
                #print day_data.art.dose_dict
                self.assertEquals(len(day_data.art.dose_dict.keys()),
                                  2) # two doses, one for the answered, another for unchecked
                art_slast = day_data.art.dose_dict[0][0]
                art_slast_props = {
                    "encounter_date": "2012-12-07T05:00:00Z",
                    "total_doses": 2,
                    "day_note": "2nd to last last filled by questions",
                    "day_index": 1,
                    "note": "",
                    "pact_id": "999999",
                    "provider": "ctsims",
                    "method": "pillbox",
                    "observed_date": "2012-12-06T05:00:00Z",
                    "day_slot": -1,
                    "completed_date": "2012-12-16T22:00:28Z",
                    "adherence": "partial",
                    "dose_number": 0,
                    #                    "doc_type": "CObservation",
                    "is_reconciliation": False,
                    "anchor_date": "2012-12-07T05:00:00Z",
                    "created_date": "2012-12-16T21:37:52Z",
                    "is_art": True,
                    "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                    "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                }
                check_obs_props(art_slast, art_slast_props)

                nonart_slast0 = day_data.nonart.dose_dict[0][0]
                non_art0 = {
                    "encounter_date": "2012-12-07T05:00:00Z",
                    "total_doses": 3,
                    "day_note": "",
                    "day_index": 1,
                    "note": "",
                    "pact_id": "999999",
                    "provider": "ctsims",
                    "method": "direct",
                    "observed_date": "2012-12-06T05:00:00Z",
                    #                "day_slot": -1,
                    "completed_date": "2012-12-16T22:00:28Z",
                    "adherence": "empty",
                    "dose_number": 0,
                    #                "doc_type": "CObservation",
                    "is_reconciliation": False,
                    "anchor_date": "2012-12-07T05:00:00Z",
                    "created_date": "2012-12-16T21:37:52Z",
                    "is_art": False,
                    "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                    "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                }
                check_obs_props(nonart_slast0, non_art0)

                nonart_slast1 = day_data.nonart.dose_dict[1][0]
                non_art1 = {
                    "encounter_date": "2012-12-07T05:00:00Z",
                    "total_doses": 3,
                    "day_note": "non art noon second to last",
                    "day_index": 1,
                    "note": "",
                    "pact_id": "999999",
                    "provider": "ctsims",
                    "method": "pillbox",
                    "observed_date": "2012-12-06T05:00:00Z",
                    #                "day_slot": -1,
                    "completed_date": "2012-12-16T22:00:28Z",
                    "adherence": "partial",
                    "dose_number": 1,
                    #                "doc_type": "CObservation",
                    "is_reconciliation": False,
                    "anchor_date": "2012-12-07T05:00:00Z",
                    "created_date": "2012-12-16T21:37:52Z",
                    "is_art": False,
                    "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                    "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                }
                check_obs_props(nonart_slast1, non_art1)

                nonart_slast2 = day_data.nonart.dose_dict[2][0]
                non_art2 = {
                    "encounter_date": "2012-12-07T05:00:00Z",
                    "total_doses": 3,
                    "day_note": "art evening second to last",
                    "day_index": 1,
                    "note": "",
                    "pact_id": "999999",
                    "provider": "ctsims",
                    "method": "pillbox",
                    "observed_date": "2012-12-06T05:00:00Z",
                    #                "day_slot": -1,
                    "completed_date": "2012-12-16T22:00:28Z",
                    "adherence": "partial",
                    "dose_number": 2,
                    #                "doc_type": "CObservation",
                    "is_reconciliation": False,
                    "anchor_date": "2012-12-07T05:00:00Z",
                    "created_date": "2012-12-16T21:37:52Z",
                    "is_art": False,
                    "_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759",
                    "doc_id": "a1811d7e-c968-4b63-aea5-6195ce0d8759"
                }
                check_obs_props(nonart_slast2, non_art2)

            if this_day.date() == ANCHOR_DATE.date():
                self.assertEqual(len(day_data.nonart.dose_dict[0]), 1)
                non_art_last = day_data.nonart.dose_dict[0][0]
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

                non_art_last_noon = day_data.nonart.dose_dict[1][0]
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
                check_obs_props(non_art_last_noon, non_art_last_noon_props)
                #todo: check reconciliation?
            pass
            #outside for
