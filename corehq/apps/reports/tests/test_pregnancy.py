#from django.test import TestCase
#from django.conf import settings
#from couchdbkit import *
#from dimagi.utils.data import random_clinic_id, random_person
#import os
#from bhoma.apps.xforms.util import post_xform_to_couch
#from bhoma.apps.patient.processing import add_form_to_patient, new_form_received,\
#    new_form_workflow
#from bhoma.apps.reports.models import CPregnancy
#from bhoma.apps.patient.models.couch import CPatient
#
#
#class PregnancyTest(TestCase):
#
#    def setUp(self):
#        pass
#
#    def testHIVTestDone(self):
#        # no hiv on first visit
#        p = random_person()
#        p.save()
#        post_and_process_xform("preg_no_hiv_test_1.xml", p)
#        pregnancy = CPregnancy.view("reports/pregnancies_for_patient", key=p.get_id).one()
#        self.assertEqual(False, pregnancy.hiv_test_done)
#
#        # but add it on a subsequent visit
#        post_and_process_xform("preg_hiv_neg_2.xml", p)
#        pregnancy = CPregnancy.view("reports/pregnancies_for_patient", key=p.get_id).one()
#        self.assertEqual(True, pregnancy.hiv_test_done)
#
#        p2 = random_person()
#        p2.save()
#        post_and_process_xform("preg_hiv_neg_1.xml", p2)
#        pregnancy = CPregnancy.view("reports/pregnancies_for_patient", key=p2.get_id).one()
#        self.assertEqual(True, pregnancy.hiv_test_done)
#
#
#    def testNVP(self):
#        # cases are:
#        # Not testing positive, (0, 0)
#        # Testing positive no NVP (1, 0)
#        # Testing positive, NVP (1, 1)
#
#        p = random_person()
#        p.save()
#        post_and_process_xform("preg_no_hiv_test_1.xml", p)
#        pregnancy = CPregnancy.view("reports/pregnancies_for_patient", key=p.get_id).one()
#        self.assertEqual(False, pregnancy.ever_tested_positive)
#
#        post_and_process_xform("preg_hiv_pos_2.xml", p)
#        pregnancy = CPregnancy.view("reports/pregnancies_for_patient", key=p.get_id).one()
#        self.assertEqual(True, pregnancy.ever_tested_positive)
#
#        p2 = random_person()
#        p2.save()
#        # but add it on a subsequent visit
#        post_and_process_xform("preg_hiv_pos_1.xml", p2)
#        pregnancy = CPregnancy.view("reports/pregnancies_for_patient", key=p2.get_id).one()
#        self.assertEqual(True, pregnancy.ever_tested_positive)
#
#        p3 = random_person()
#        p3.save()
#        # but add it on a subsequent visit
#        post_and_process_xform("preg_hiv_prev_pos_1.xml", p3)
#        pregnancy = CPregnancy.view("reports/pregnancies_for_patient", key=p3.get_id).one()
#        self.assertEqual(True, pregnancy.ever_tested_positive)
#
#
#def post_and_process_xform(filename, patient):
#    doc = post_xform(filename, patient.get_id)
#    new_form_workflow(doc, "unit_tests", patient.get_id)
#    return doc
#
#
#def post_xform(filename, patient_id):
#    file_path = os.path.join(os.path.dirname(__file__), "data", filename)
#    with open(file_path, "rb") as f:
#        xml_data = f.read()
#    xml_data = xml_data.replace("REPLACE_PATID", patient_id)
#    doc = post_xform_to_couch(xml_data)
#    return doc
#
#