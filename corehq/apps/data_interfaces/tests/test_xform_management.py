from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest, QueryDict
from django.test import TestCase, Client

from corehq.apps.data_interfaces.views import XFormManagementView
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import WebUser
from corehq.apps.es.users import user_adapter
from corehq.apps.es.forms import form_adapter


@es_test(requires=[form_adapter, user_adapter], setup_class=True)
class XFormManagementTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain('xform-management-test')
        cls.web_user = WebUser.create('xform-management-test', 'test', 'test', None, None,
                                      is_superuser=True)
        Client().force_login(cls.web_user.get_django_user())

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()

    def test_get_xform_ids__sanity_check(self):
        # This helper has to mock a request in a brittle way.
        # If permissions are wrong, instead of returning a list,
        # it will return an HttpResponse containing the permission error.
        # This can break when permissions change.
        # So, just test that we aren't hitting that situation and that the response is a list.
        request = HttpRequest()
        request.POST = QueryDict('select_all=')
        request.couch_user = self.web_user
        SessionMiddleware(self.fail).process_request(request)
        view = XFormManagementView()
        view.args = (self.domain.name,)
        view.request = request
        assert isinstance(view.get_xform_ids(request), list)
