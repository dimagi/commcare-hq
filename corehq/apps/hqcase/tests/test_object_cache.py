import StringIO
import hashlib
import os
import time

from django.test.client import Client
from django.utils import http

from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.dbaccessors import get_all_forms_in_all_domains

from corehq.apps.users.models import WebUser
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import TEST_CASE_ID, BaseCaseMultimediaTest, MEDIA_FILES, TEST_DOMAIN
from couchforms.models import XFormInstance


TEST_USER = 'case_attachment@hqtesting.com'

TEST_PASSWORD = 'testing'

def hack_local_url(url):
    #hack, in tests, this is the in built sites which is not useful externally
    local_url = '/'.join(url.split('/')[3:])
    return local_url


def rebuild_stream(response_iter):
    data = StringIO.StringIO()
    try:
        while True:
            payload = response_iter.next()
            if payload:
                data.write(payload)
    except StopIteration:
        pass
    data.seek(0)
    return data



class CaseObjectCacheTest(BaseCaseMultimediaTest):
    """
    test case object caching - for case-attachments and api access.
    """

    def setUp(self):
        self.domain = Domain.get_or_create_with_name(TEST_DOMAIN, is_active=True)
        self.user = WebUser.create(TEST_DOMAIN, TEST_USER, TEST_PASSWORD)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()
        for item in CommCareCase.view("case/by_user", include_docs=True, reduce=False).all():
            item.delete()
        for item in get_all_forms_in_all_domains():
            item.delete()
        time.sleep(1)

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def testGenericObjectCache(self):
        """
        Generic caching framework for assets that need downloads, like jad/jars
        """
        #API url not implemented yet, leaving this stub in as placeholder todo for full implementation
        pass

    def testCreateMultimediaCase(self):
        """
        Verify that URL for case attachment api uses the right view and returns at least the original attachments correclty.
        """
        attachments = ['dimagi_logo_file', 'commcare_logo_file']

        self._doCreateCaseWithMultimedia(attachments=attachments)
        case = CommCareCase.get(TEST_CASE_ID)
        case.domain = TEST_DOMAIN
        self.assertEqual(2, len(case.case_attachments))
        client = Client()
        client.login(username=TEST_USER, password=TEST_PASSWORD)
        for a in attachments:
            url = '/%s' % hack_local_url(case.get_attachment_server_url(a))
            data = client.get(url, follow=True)
            content = rebuild_stream(data.streaming_content)
            self.assertEqual(hashlib.md5(self._attachmentFileStream(a).read()).hexdigest(),
                             hashlib.md5(content.read()).hexdigest())
