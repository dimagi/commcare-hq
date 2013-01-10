from django.test.client import Client
from django.test import TestCase
from receiver.util import spoof_submission
import uuid
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.domain.shortcuts import create_domain
from django.core.urlresolvers import reverse
from corehq.apps.users.models import WebUser
from couchforms.models import XFormInstance
from couchexport.export import ExportConfiguration
import time
from couchexport.models import ExportSchema

FORM_TEMPLATE = """<?xml version='1.0' ?>
<foo xmlns:jrm="http://openrosa.org/jr/xforms" xmlns="http://www.commcarehq.org/export/test">
<meta>
    <uid>%(uid)s</uid>
</meta>
</foo>
"""

DOMAIN = "test"

def get_form():
    return FORM_TEMPLATE % {"uid": uuid.uuid4().hex}
    
def submit_form(f=None, domain=DOMAIN):
    if f is None:
        f = get_form()
    url = get_submit_url(domain)
    return spoof_submission(url, f, hqsubmission=False)

def get_export_response(client, previous="", include_errors=False):
    # e.g. /a/wvtest/reports/export/?export_tag=%22http://openrosa.org/formdesigner/0B5AEAF6-0394-4E4B-B2FD-6CDDE1BCBC8D%22
    return client.get(reverse("corehq.apps.reports.views.export_data", 
                            args=[DOMAIN]),
                 {"export_tag": '"http://www.commcarehq.org/export/test"',
                  "previous_export": previous,
                  "include_errors": include_errors,
                  "format": "html",
                  "use_cache": False})

class ExportTest(TestCase):
    
    def _clear_docs(self):
        config = ExportConfiguration(XFormInstance.get_db(),
                                     [DOMAIN, "http://www.commcarehq.org/export/test"])
        for form in config.get_docs():
            XFormInstance.wrap(form).delete()

    def setUp(self):
        self._clear_docs()
        create_domain(DOMAIN)
        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(DOMAIN, is_admin=True)
        self.couch_user.save()
        
    def tearDown(self):
        self.couch_user.delete()
        self._clear_docs()

    def testExportTokenMigration(self):
        c = Client()
        c.login(**{'username': 'test', 'password': 'foobar'})

        submit_form()
        time.sleep(1)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.content is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)

        # blow away the timestamp property to ensure we're testing the
        # migration case
        prev_token = resp["X-CommCareHQ-Export-Token"]
        prev_checkpoint = ExportSchema.get(prev_token)
        assert prev_checkpoint.timestamp
        prev_checkpoint.timestamp = None
        prev_checkpoint.save()
        prev_checkpoint = ExportSchema.get(prev_token)
        assert not prev_checkpoint.timestamp 

        # data but no new data = redirect
        resp = get_export_response(c, prev_token)
        self.assertEqual(302, resp.status_code)

        submit_form()
        time.sleep(1)
        resp = get_export_response(c, prev_token)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.content is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)
        prev_token = resp["X-CommCareHQ-Export-Token"]

        full_data = get_export_response(c).content
        partial_data = get_export_response(c, prev_token).content
        self.assertTrue(len(full_data) > len(partial_data))

    def testExportTokens(self):
        c = Client()
        c.login(**{'username': 'test', 'password': 'foobar'})
        # no data = redirect
        resp = get_export_response(c)
        self.assertEqual(302, resp.status_code)
        
        # data = data
        submit_form()

        # now that this is time based we have to sleep first. this is annoying
        time.sleep(1)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.content is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)
        prev_token = resp["X-CommCareHQ-Export-Token"]
        
        # data but no new data = redirect
        resp = get_export_response(c, prev_token)
        self.assertEqual(302, resp.status_code)

        submit_form()
        time.sleep(1)
        resp = get_export_response(c, prev_token)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.content is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)
        prev_token = resp["X-CommCareHQ-Export-Token"]
        
        full_data = get_export_response(c).content
        partial_data = get_export_response(c, prev_token).content
        self.assertTrue(len(full_data) > len(partial_data))
        
    def testExportFilter(self):
        c = Client()
        c.login(**{'username': 'test', 'password': 'foobar'})
        
        # initially nothing
        self.assertEqual(302, get_export_response(c).status_code)
        
        # submit, assert something
        f = get_form()
        submit_form(f)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        initial_content = resp.content
        
        # resubmit, assert same since it's a dupe
        submit_form(f)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        # hack: check for the number of rows to ensure the new one 
        # didn't get added. They aren't exactly the same because the
        # duplicate adds to the schema.
        self.assertEqual(initial_content.count("<tr>"), 
                         resp.content.count("<tr>"))
        
        # unless we explicitly include errors
        resp = get_export_response(c, include_errors=True)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(len(resp.content) > len(initial_content))
        
        