import StringIO
import hashlib
import time

from django.test.client import Client

from corehq.apps.domain.models import Domain

from corehq.apps.users.models import WebUser
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import TEST_CASE_ID, BaseCaseMultimediaTest, delete_all_cases, delete_all_xforms
from casexml.apps.case.tests.util import TEST_DOMAIN_NAME


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
        self.domain = Domain.get_or_create_with_name(TEST_DOMAIN_NAME, is_active=True)
        self.user = WebUser.create(TEST_DOMAIN_NAME, TEST_USER, TEST_PASSWORD)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()
        delete_all_cases()
        delete_all_xforms()
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
        case.domain = TEST_DOMAIN_NAME
        self.assertEqual(2, len(case.case_attachments))
        client = Client()
        client.login(username=TEST_USER, password=TEST_PASSWORD)
        for a in attachments:
            url = '/%s' % hack_local_url(case.get_attachment_server_url(a))
            data = client.get(url, follow=True)
            content = rebuild_stream(data.streaming_content)
            self.assertEqual(hashlib.md5(self._attachmentFileStream(a).read()).hexdigest(),
                             hashlib.md5(content.read()).hexdigest())
