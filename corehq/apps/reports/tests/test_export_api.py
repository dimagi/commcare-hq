from django.test.client import Client
from couchforms.util import spoof_submission
import uuid
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.domain.shortcuts import create_domain
from django.core.urlresolvers import reverse
from corehq.apps.users.models import WebUser
from couchforms.models import XFormInstance
from couchexport.export import ExportConfiguration
import time
from couchexport.models import ExportSchema

from corehq.apps.accounting.tests import BaseAccountingTest
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.domain.models import Domain

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


def _submit_form(f=None, domain=DOMAIN):
    if f is None:
        f = get_form()
    url = get_submit_url(domain)
    return spoof_submission(url, f)


def get_export_response(client, previous="", include_errors=False, domain=DOMAIN):
    # e.g. /a/wvtest/reports/export/?export_tag=%22http://openrosa.org/formdesigner/0B5AEAF6-0394-4E4B-B2FD-6CDDE1BCBC8D%22
    return client.get(
        reverse("corehq.apps.reports.views.export_data", args=[domain]),
        {
            "export_tag": '"http://www.commcarehq.org/export/test"',
            "previous_export": previous,
            "include_errors": include_errors,
            "format": "html",
            "use_cache": False
        }
    )


def _content(streaming_response):
    return ''.join(streaming_response.streaming_content)


class ExportTest(BaseAccountingTest, DomainSubscriptionMixin):

    def _clear_docs(self):
        config = ExportConfiguration(XFormInstance.get_db(),
                                     [DOMAIN, "http://www.commcarehq.org/export/test"])
        for form in config.get_docs():
            XFormInstance.wrap(form).delete()

    def setUp(self):
        self._clear_docs()
        self.domain = create_domain(DOMAIN)
        self.setup_subscription(self.domain.name, SoftwarePlanEdition.ADVANCED)

        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(DOMAIN, is_admin=True)
        self.couch_user.save()

    def tearDown(self):
        self.couch_user.delete()
        self._clear_docs()

        self.teardown_subscription()

        super(ExportTest, self).tearDown()

    def testExportTokenMigration(self):
        c = Client()
        c.login(**{'username': 'test', 'password': 'foobar'})

        _submit_form()
        time.sleep(1)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(_content(resp) is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)

        # blow away the timestamp property to ensure we're testing the
        # migration case
        prev_token = resp["X-CommCareHQ-Export-Token"]
        prev_checkpoint = ExportSchema.get(prev_token)
        assert prev_checkpoint.timestamp

    def testExportTokens(self):
        c = Client()
        c.login(**{'username': 'test', 'password': 'foobar'})
        # no data = redirect
        resp = get_export_response(c)
        self.assertEqual(302, resp.status_code)
        
        # data = data
        _submit_form()

        # now that this is time based we have to sleep first. this is annoying
        time.sleep(1)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(_content(resp) is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)
        prev_token = resp["X-CommCareHQ-Export-Token"]
        
        # data but no new data = redirect
        resp = get_export_response(c, prev_token)
        self.assertEqual(302, resp.status_code)

        _submit_form()
        time.sleep(1)
        resp = get_export_response(c, prev_token)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(_content(resp) is not None)
        self.assertTrue("X-CommCareHQ-Export-Token" in resp)

    def testExportFilter(self):
        c = Client()
        c.login(**{'username': 'test', 'password': 'foobar'})
        
        # initially nothing
        self.assertEqual(302, get_export_response(c).status_code)
        
        # submit, assert something
        f = get_form()
        _submit_form(f)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        initial_content = _content(resp)
        
        # resubmit, assert same since it's a dupe
        _submit_form(f)
        resp = get_export_response(c)
        self.assertEqual(200, resp.status_code)
        # hack: check for the number of rows to ensure the new one 
        # didn't get added. They aren't exactly the same because the
        # duplicate adds to the schema.
        content = _content(resp)
        self.assertEqual(initial_content.count("<tr>"), 
                         content.count("<tr>"))
        
        # unless we explicitly include errors
        resp = get_export_response(c, include_errors=True)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(len(_content(resp)) > len(initial_content))

    def test_no_subscription(self):
        """
        Tests authorization function properly blocks domains without proper subscription
        :return:
        """
        community_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        new_user = WebUser.create(community_domain.name, 'test2', 'testpass')
        new_user.save()
        c = Client()
        c.login(**{'username': 'test2', 'password': 'testpass'})
        f = get_form()
        _submit_form(f, community_domain.name)
        resp = get_export_response(c, domain=community_domain.name)
        self.assertEqual(401, resp.status_code)

        community_domain.delete()
        new_user.delete()
