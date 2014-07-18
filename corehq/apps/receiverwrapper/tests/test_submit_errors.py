from django.test import TestCase
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
from django.test.client import Client
from django.core.urlresolvers import reverse
import os
from dimagi.utils.post import tmpfile
from couchforms.models import SubmissionErrorLog
from couchforms.signals import successful_form_received


def _clear_all_forms(domain):
    for item in SubmissionErrorLog.view("couchforms/all_submissions_by_domain",
                                  reduce=False,
                                  include_docs=True,
                                  startkey=[domain, "by_type"],
                                  endkey=[domain, "by_type", {}],
                                  wrapper=lambda row: SubmissionErrorLog.wrap(row['doc'])).all():

        item.delete()

class SubmissionErrorTest(TestCase):
    
    def setUp(self):
        self.domain = create_domain("submit-errors")
        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(self.domain.name, is_admin=True)
        self.couch_user.save()
        self.client = Client()
        self.client.login(**{'username': 'test', 'password': 'foobar'})
        self.url = reverse("receiver_post", args=[self.domain])
        _clear_all_forms(self.domain.name)
        
    def tearDown(self):
        self.couch_user.delete()
        self.domain.delete()
        _clear_all_forms(self.domain.name)
    
    def _submit(self, formname):
        file_path = os.path.join(os.path.dirname(__file__), "data", formname)
        with open(file_path, "rb") as f:
            return self.client.post(self.url, {
                "xml_submission_file": f
            })
        
    def testSubmitBadAttachmentType(self):
        res = self.client.post(self.url, {
                "xml_submission_file": "this isn't a file"
        })
        self.assertEqual(400, res.status_code)
        self.assertIn("xml_submission_file", res.content)
            
    def testSubmitDuplicate(self):
        file = os.path.join(os.path.dirname(__file__), "data", "simple_form.xml")
        with open(file) as f:
            res = self.client.post(self.url, {
                    "xml_submission_file": f
            })
            self.assertEqual(201, res.status_code)
            self.assertIn("Thanks for submitting", res.content)
        
        with open(file) as f:
            res = self.client.post(self.url, {
                    "xml_submission_file": f
            })
            self.assertEqual(201, res.status_code)
            self.assertIn("Form is a duplicate", res.content)
        
        # make sure we logged it
        log = SubmissionErrorLog.view("couchforms/all_submissions_by_domain",
                                      reduce=False,
                                      include_docs=True,
                                      startkey=[self.domain.name, "by_type", "XFormDuplicate"],
                                      endkey=[self.domain.name, "by_type", "XFormDuplicate", {}],
                                      classes={'XFormDuplicate': SubmissionErrorLog}).one()
        
        self.assertTrue(log is not None)
        self.assertIn("Form is a duplicate", log.problem)
        with open(file) as f:
            self.assertEqual(f.read(), log.get_xml())
        
            
    def testSubmissionError(self):
        evil_laugh = "mwa ha ha!"
        
        def fail(sender, xform, **kwargs):
            raise Exception(evil_laugh)
        
        successful_form_received.connect(fail)
        
        try:    
            file = os.path.join(os.path.dirname(__file__), "data",
                                "simple_form.xml")
            with open(file) as f:
                res = self.client.post(self.url, {
                    "xml_submission_file": f
                })
                self.assertEqual(201, res.status_code)
                self.assertIn(evil_laugh, res.content)

            # make sure we logged it
            log = SubmissionErrorLog.view(
                "couchforms/all_submissions_by_domain",
                reduce=False,
                include_docs=True,
                startkey=[self.domain.name, "by_type", "XFormError"],
                endkey=[self.domain.name, "by_type", "XFormError", {}],
            ).one()

            self.assertTrue(log is not None)
            self.assertIn(evil_laugh, log.problem)
            with open(file) as f:
                self.assertEqual(f.read(), log.get_xml())
        
        finally:
            successful_form_received.disconnect(fail)
            
    def testSubmitBadXML(self):
        f, path = tmpfile()
        with f:
            f.write("this isn't even close to xml")
        with open(path) as f:
            res = self.client.post(self.url, {
                    "xml_submission_file": f
            })
            self.assertEqual(500, res.status_code)
            self.assertIn('Invalid XML', res.content)
        
        # make sure we logged it
        log = SubmissionErrorLog.view("couchforms/all_submissions_by_domain",
                                      reduce=False,
                                      include_docs=True,
                                      startkey=[self.domain.name, "by_type", "SubmissionErrorLog"],
                                      endkey=[self.domain.name, "by_type", "SubmissionErrorLog", {}]).one()
        
        self.assertTrue(log is not None)
        self.assertIn('Invalid XML', log.problem)
        self.assertEqual("this isn't even close to xml", log.get_xml())
        
