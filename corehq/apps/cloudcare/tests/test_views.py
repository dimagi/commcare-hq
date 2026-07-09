from django.test import RequestFactory, SimpleTestCase

from corehq.apps.app_manager.models import (
    PublicFormSession,
    PublicFormUser,
    PublicWebform,
)
from corehq.apps.cloudcare.views import FormplayerMain


class GetRestoreAsUserTests(SimpleTestCase):

    def _public_form_request(self):
        webform = PublicWebform(domain='public-forms-domain')
        session = PublicFormSession(public_webform=webform)
        request = RequestFactory().get('/')
        request.couch_user = PublicFormUser(session)
        return request

    def test_public_form_session_returns_itself(self):
        request = self._public_form_request()
        user, set_cookie = FormplayerMain.get_restore_as_user(request, 'public-forms-domain')
        assert user is request.couch_user

    def test_public_form_session_set_cookie_is_noop(self):
        request = self._public_form_request()
        _, set_cookie = FormplayerMain.get_restore_as_user(request, 'public-forms-domain')
        response = object()
        assert set_cookie(response) is response
