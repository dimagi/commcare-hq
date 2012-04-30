from django.test import TestCase
import os
import json
from corehq.apps.app_manager.models import import_app
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMSLog
from corehq.apps.smsforms.app import start_session, get_responses
from corehq.apps.smsforms.tests.util import MockContact


CONTACT_ID = "sms_test_contact_id"

class FormplayerApiTest(TestCase):
    # NOTE: this will only work if the formplayer is running
    
    def setUp(self):
        # bootstrap domain and a sample app
        self.domain = 'test-domain'
        Domain.get_or_create_with_name(self.domain)
        with open(os.path.join(os.path.dirname(__file__), "data", "demo_app.json")) as f:
            app_json = json.loads(f.read())
            self.app = import_app(app_json, self.domain)
            
        self.contact = MockContact(id=CONTACT_ID, username="smsform_contact",
                                   language="en")

    def test_form_playing(self):
        # start form session
        def _pl(l):
            for i in l: print i
        
        responses = start_session(self.domain, self.contact, self.app, 
                                  self.app.get_module(0), 
                                  self.app.get_module(0).get_form(0))
        
        _pl(responses)
        [answer] = responses 
        self.assertEqual("what is your name?", answer)
        
        # TODO? check state of model
        
        # play through the form, checking answers
        def _q_and_a(question, answer):
            responses = get_responses(SMSLog(couch_recipient=CONTACT_ID, domain=self.domain,
                                             text=question))
            _pl(responses)
            [answer_back] = responses
            self.assertEqual(answer, answer_back)
            
        _q_and_a("sms contact", "how old are you, sms contact?")
        _q_and_a("29", "what is your gender? 1:male, 2:female")
        _q_and_a("2", "thanks for submitting!")
        