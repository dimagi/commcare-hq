from django.test import TestCase
import os
import json
from corehq.apps.app_manager.models import import_app
from corehq.apps.domain.models import Domain
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.tests.util import MockContact, CONTACT_ID, q_and_a
from corehq.apps.smsforms.models import XFormsSession
from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase

class FormplayerApiTest(TestCase):
    # NOTE: this will only work if the formplayer is running
    
    def setUp(self):
        # bootstrap domain and a sample app
        self.domain = 'test-domain'
        Domain.get_or_create_with_name(self.domain)
        self.contact = MockContact(id=CONTACT_ID, username="smsform_contact",
                                   language="en")
        
    def test_basic_form_playing(self):
        # load the app
        with open(os.path.join(os.path.dirname(__file__), "data", "demo_app.json")) as f:
            app_json = json.loads(f.read())
            app = import_app(app_json, self.domain)
            
        # start form session
        session, responses = start_session(self.domain, self.contact, app, 
                                           app.get_module(0), 
                                           app.get_module(0).get_form(0))
        
        [answer] = responses 
        self.assertEqual("what is your name?", answer)
        
        # check state of model
        self.assertEqual(session.start_time, session.modified_time)
        self.assertEqual("http://www.commcarehq.org/tests/smsforms", session.form_xmlns)
        self.assertFalse(session.end_time)
        self.assertEqual(False, session.completed)
        self.assertEqual(self.domain, session.domain)
        self.assertEqual(self.contact.get_id, session.user_id)
        self.assertEqual(app.get_id, session.app_id)
        self.assertFalse(session.submission_id)
        
        # play through the form, checking answers
        q_and_a(self, "sms contact", "how old are you, sms contact?", self.domain)
        q_and_a(self, "29", "what is your gender? 1:male, 2:female", self.domain)
        q_and_a(self, "2", "thanks for submitting!", self.domain)
        
        # check the instance
        session = XFormsSession.get(session.get_id)
        self.assertTrue(session.submission_id)
        instance = XFormInstance.get(session.submission_id)
        self.assertEqual("sms contact", instance.xpath("form/name"))
        self.assertEqual("29", instance.xpath("form/age"))
        self.assertEqual("f", instance.xpath("form/gender"))
        self.assertEqual(self.domain, instance.domain)
        
    def test_case_integration(self):
        # load the app
        with open(os.path.join(os.path.dirname(__file__), "data", "app_with_cases.json")) as f:
            app_json = json.loads(f.read())
            app = import_app(app_json, self.domain)
            
        # the first form opens the case
        session, responses = start_session(self.domain, self.contact, app, 
                                           app.get_module(0), 
                                           app.get_module(0).get_form(0))
        
        [answer] = responses 
        self.assertEqual("what's the case name?", answer)
        q_and_a(self, "some case", "thanks, you're done!", self.domain)
        
        def _get_case(session):
            session = XFormsSession.get(session.get_id)
            self.assertTrue(session.submission_id)
            instance = XFormInstance.get(session.submission_id)
            case_id = instance.xpath("form/case/@case_id")
            self.assertTrue(case_id)
            return CommCareCase.get(case_id)
        
        # check the case
        case = _get_case(session)
        self.assertEqual("some case", case.name)
        self.assertFalse(case.closed)
        self.assertFalse(hasattr(case, "feeling"))
        
        # the second form updates the case
        # NOTE: this currently fails for several reasons, the most
        # notable being that there needs to be a server running configured
        # to hit the test DB, and that there's no authentication built in
        session, responses = start_session(self.domain, self.contact, app, 
                                           app.get_module(0), 
                                           app.get_module(0).get_form(1),
                                           case_id=case.get_id)
        
        [answer] = responses 
        self.assertEqual("how you feeling, some case?", answer)
        q_and_a(self, "groovy", "thanks, you're done!", self.domain)
        
        