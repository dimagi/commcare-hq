# coding: utf-8
from django.test import TestCase
from corehq.apps.users.models import WebUser
from corehq.apps.domain.shortcuts import create_domain
from django.test.client import Client
from django.core.urlresolvers import reverse
import os

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import run_with_all_backends, FormProcessorTestUtils
from dimagi.utils.post import tmpfile
from couchforms.signals import successful_form_received


class SubmissionErrorTest(TestCase):

    def setUp(self):
        self.domain = create_domain("submit-errors")
        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(self.domain.name, is_admin=True)
        self.couch_user.save()
        self.client = Client()
        self.client.login(**{'username': 'test', 'password': 'foobar'})
        self.url = reverse("receiver_post", args=[self.domain])
        FormProcessorTestUtils.delete_all_xforms(self.domain.name)

    def tearDown(self):
        self.couch_user.delete()
        self.domain.delete()
        FormProcessorTestUtils.delete_all_xforms(self.domain.name)

    def _submit(self, formname):
        file_path = os.path.join(os.path.dirname(__file__), "data", formname)
        with open(file_path, "rb") as f:
            res = self.client.post(self.url, {
                "xml_submission_file": f
            })
            return file_path, res

    @run_with_all_backends
    def testSubmitBadAttachmentType(self):
        res = self.client.post(self.url, {
                "xml_submission_file": "this isn't a file"
        })
        self.assertEqual(400, res.status_code)
        self.assertIn("xml_submission_file", res.content)

    @run_with_all_backends
    def testSubmitDuplicate(self):
        file, res = self._submit('simple_form.xml')
        self.assertEqual(201, res.status_code)
        self.assertIn(u"   √   ".encode('utf-8'), res.content)

        file, res = self._submit('simple_form.xml')
        self.assertEqual(201, res.status_code)
        self.assertIn("Form is a duplicate", res.content)

        # make sure we logged it
        [log] = FormAccessors(self.domain.name).get_forms_by_type('XFormDuplicate', limit=1)

        self.assertIsNotNone(log)
        self.assertIn("Form is a duplicate", log.problem)
        with open(file) as f:
            self.assertEqual(f.read(), log.get_xml())

    @run_with_all_backends
    def testSubmissionError(self):
        evil_laugh = "mwa ha ha!"

        def fail(sender, xform, **kwargs):
            raise Exception(evil_laugh)

        successful_form_received.connect(fail)

        try:
            file, res = self._submit("simple_form.xml")
            self.assertEqual(201, res.status_code)
            self.assertIn(evil_laugh, res.content)

            # make sure we logged it
            [log] = FormAccessors(self.domain.name).get_forms_by_type('XFormError', limit=1)

            self.assertIsNotNone(log)
            self.assertIn(evil_laugh, log.problem)
            with open(file) as f:
                self.assertEqual(f.read(), log.get_xml())
        
        finally:
            successful_form_received.disconnect(fail)

    @run_with_all_backends
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
        [log] = FormAccessors(self.domain.name).get_forms_by_type('SubmissionErrorLog', limit=1)

        self.assertIsNotNone(log)
        self.assertIn('Invalid XML', log.problem)
        self.assertEqual("this isn't even close to xml", log.get_xml())
