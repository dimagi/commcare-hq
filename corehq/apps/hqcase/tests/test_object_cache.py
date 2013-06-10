from django.test import TestCase, RequestFactory
import ipdb
from corehq.apps.users.models import CommCareUser
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import TEST_CASE_ID, BaseCaseMultimediaTest, TEST_DOMAIN
from django.test.client import Client
from corehq.apps.api.object_fetch_api import CaseAttachmentAPI, CachedObjectAPI


TEST_USER = 'tester'
TEST_PASSWORD = 'testing'

class CaseObjectCacheTest(BaseCaseMultimediaTest):
    """
    test case object caching
    """

    def setUp(self):
        self.user = CommCareUser.create(TEST_DOMAIN, TEST_USER, TEST_PASSWORD)

    def tearDown(self):
        self.user.delete()

    def testGenericObjectCache(self):
        """
        Generic caching framework for assets that need downloads, like jad/jars
        """
        pass

    def _ref_get(self, url):
        rf = RequestFactory()
        req = rf.get(url)
        attach_api = CaseAttachmentAPI()
        return attach_api.get(req, 'tester')


    def testCreateMultimediaCase(self):
        attachments = ['dimagi_logo', 'commcare_logo']

        self._doCreateCaseWithMultimedia(attachments=attachments)
        case = CommCareCase.get(TEST_CASE_ID)
        self.assertEqual(2, len(case.case_attachments))
        c = Client()
        lresponse = c.post('/login/', {'username': TEST_USER, 'password': TEST_PASSWORD})

        for a in attachments:
            url = case.get_attachment_server_url(a)
            ipdb.set_trace()
            data = c.get(url)



