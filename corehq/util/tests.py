from django.test import TestCase
from corehq.util.couch import get_document_or_404
from corehq.apps.users.models import WebUser
from corehq.apps.users.models import CommCareUser


class GetDocTestCase(TestCase):
    def setUp(self):
        self.web_user = WebUser.create('test', 'test', 'test')
        self.commcare_user = CommCareUser.create('test',
                                                 'commcaretest',
                                                 'test')

    def tearDown(self):
        self.web_user.delete()
        self.commcare_user.delete()

    def test_get_web_user(self):
        get_document_or_404(WebUser, 'test', self.web_user._id)

    def test_get_commcare_user(self):
        get_document_or_404(CommCareUser, 'test', self.commcare_user._id)
