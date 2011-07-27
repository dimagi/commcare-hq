from django.test.client import Client
from django.test import TestCase
from receiver.util import spoof_submission
import uuid
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.domain.shortcuts import create_domain, create_user
from django.core.urlresolvers import reverse
from corehq.apps.users.models import CouchUser

FORM_TEMPLATE = """<?xml version='1.0' ?>
<foo xmlns:jrm="http://openrosa.org/jr/xforms" xmlns="http://www.commcarehq.org/export/test">
<meta>
    <uid>%(uid)s</uid>
</meta>
</foo>
"""

DOMAIN = "test"

def submit_form(domain=DOMAIN):
    url = get_submit_url(domain)
    submission = FORM_TEMPLATE % {"uid": uuid.uuid4()}
    return spoof_submission(url, submission, hqsubmission=True)

def get_export_response(client, previous=""):
    # e.g. /a/wvtest/reports/export/?export_tag=%22http://openrosa.org/formdesigner/0B5AEAF6-0394-4E4B-B2FD-6CDDE1BCBC8D%22
    return client.get(reverse("corehq.apps.reports.views.export_data", 
                            args=[DOMAIN]),
                 {"export_tag": '"http://www.commcarehq.org/export/test"',
                  "previous_export": previous})

class ExportTest(TestCase):
    
    def setUp(self):
        dom = create_domain(DOMAIN)
        user = create_user("test", "foobar")
        couch_user = CouchUser.from_web_user(user)
        couch_user.add_domain_membership(DOMAIN, is_admin=True)
        couch_user.save()
        
    
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