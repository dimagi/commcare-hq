from django.utils.unittest.case import TestCase
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
from django.test.client import Client
from django.core.urlresolvers import reverse
from StringIO import StringIO
import os

class SubmissionTest(TestCase):
    def setUp(self):
        self.domain = create_domain("submit")
        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(self.domain.name, is_admin=True)
        self.couch_user.save()
        self.client = Client()
        self.client.login(**{'username': 'test', 'password': 'foobar'})
        self.url = reverse("receiver_post", args=[self.domain])
        
    def tearDown(self):
        self.couch_user.delete()
        self.domain.delete()
        
    def _submit(self, formname):
        file_path = os.path.join(os.path.dirname(__file__), "data", formname)
        with open(file_path, "rb") as f:
            return self.client.post(self.url, {
                "xml_submission_file": f
            })
        
    def _check_for_message(self, msg, response):
        # ghetto
        if msg in str(response):
            return True
        else:
            # just so there's a printout
            self.assertEqual(msg, str(response))
        
    
    def testSubmitSimpleForm(self):
        self.assertTrue(self._check_for_message("Thanks for submitting, someuser.  We have received 1 forms from you today (1 forms all time)", 
                                                self._submit("simple_form.xml")),
                        "Basic form successfully parsed")
    
    def testSubmitBareForm(self):
        self.assertTrue(self._check_for_message("Thanks for submitting!", 
                                                self._submit("bare_form.xml")),
                        "Bare form successfully parsed")
    
    def testSubmitUserRegistration(self):
        self.assertTrue(self._check_for_message("Thanks for registering! Your username is mealz@", 
                                                self._submit("user_registration.xml")),
                        "User registration form successfully parsed")
    
    def testSubmitWithCase(self):
        self.assertTrue(self._check_for_message("Thanks for submitting, someuser.  We have received 1 forms from you today (1 forms all time)", 
                                                self._submit("form_with_case.xml")),
                        "Form with case successfully parsed")
    
    def testSubmitWithNamespacedMeta(self):
        self.assertTrue(self._check_for_message("Thanks for submitting, ctest.  We have received 1 forms from you today (1 forms all time)", 
                                                self._submit("namespace_in_meta.xml")),
                        "Form with namespace in meta successfully parsed")
        