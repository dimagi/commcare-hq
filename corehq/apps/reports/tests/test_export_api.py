from django.test.client import Client
from django.test import TestCase
from receiver.util import spoof_submission
import uuid
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.domain.shortcuts import create_domain, create_user
from django.core.urlresolvers import reverse
from corehq.apps.users.models import CouchUser
from couchforms.models import XFormInstance
from couchexport.schema import get_docs

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
                  "include_errors": include_errors})

class ExportTest(TestCase):
    
    def setUp(self):
        for form in get_docs([DOMAIN, "http://www.commcarehq.org/export/test"]):
            XFormInstance.wrap(form).delete()
        dom = create_domain(DOMAIN)
        user = create_user("test", "foobar")
        couch_user = CouchUser.from_web_user(user)
        couch_user.add_domain_membership(DOMAIN, is_admin=True)
        couch_user.save()
        
    def tearDown(self):
        for form in get_docs([DOMAIN, "http://www.commcarehq.org/export/test"]):
            XFormInstance.wrap(form).delete()
        
    def testExportTokens(self):
        c = Client()
        c.login(**{'username': 'test', 'password': 'foobar'})
        # no data = redirect
        resp = get_export_response(c)
        self.assertEqual(302, resp.status_code)
        
        # data = data
        submit_form()
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.content is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)
        prev_token = resp["X-CommCareHQ-Export-Token"]
        
        # data but no new data = redirect
        resp = get_export_response(c, prev_token)
        self.assertEqual(302, resp.status_code)
        
        submit_form()
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
        self.assertEqual(initial_content, resp.content)
        
        # unless we explicitly include errors
        resp = get_export_response(c, include_errors=True)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(len(resp.content) > len(initial_content))
        
        