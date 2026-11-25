import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from corehq.apps.public_webforms.decorators import (
    PUBLIC_FORM_SESSION_COOKIE_NAME,
    PUBLIC_FORM_SESSION_HEADER,
    allow_public_form_session,
)
from corehq.apps.public_webforms.models import PublicFormUser, PublicWebform
from corehq.apps.public_webforms.tests.utils import (
    create_session,
    formplayer_origin_headers,
)
from corehq.apps.users.util import PUBLIC_USER_ID


@patch(
    'corehq.apps.public_webforms.decorators.public_webforms_enabled',
    new=lambda domain: True,
)
class AllowPublicFormSessionTests(TestCase):

    def setUp(self):
        super().setUp()
        self.existing_user = object()
        future_expiration = datetime.datetime.today() + datetime.timedelta(days=30)
        self.webform = PublicWebform.objects.create(
            domain='public-forms-domain',
            app_id='app',
            app_build_id='build',
            form_unique_id='form',
            endpoint_id='endpoint',
            session_type='survey',
            allow_sms=False,
            allow_email=True,
            expires_at=future_expiration,
        )
        self.session = create_session(self.webform, expires_at=future_expiration)
        self.factory = RequestFactory()

    def _request(self, with_header=True, cookie_value=None, from_formplayer=True):
        headers = {PUBLIC_FORM_SESSION_HEADER: 'true'} if with_header else {}
        if from_formplayer:
            headers.update(formplayer_origin_headers())
        request = self.factory.post('/a/public-forms-domain/receiver/', headers=headers)
        request.couch_user = self.existing_user
        if cookie_value is not None:
            request.COOKIES[PUBLIC_FORM_SESSION_COOKIE_NAME] = cookie_value
        return request

    @staticmethod
    def _decorated_view(fallback=None):
        def view(request, domain):
            return HttpResponse('ok')
        return allow_public_form_session(view, fallback=fallback)

    def test_valid_header_and_cookie_sets_public_form_user(self):
        request = self._request(cookie_value=str(self.session.session_key))
        self._decorated_view()(request, self.webform.domain)
        assert isinstance(request.couch_user, PublicFormUser)
        assert request.couch_user.user_id == PUBLIC_USER_ID

    def test_a_session_not_from_formplayer_is_refused(self):
        request = self._request(cookie_value=str(self.session.session_key), from_formplayer=False)
        response = self._decorated_view()(request, self.webform.domain)
        assert response.status_code == 403
        assert request.couch_user is self.existing_user

    def test_a_session_not_from_formplayer_is_not_given_to_the_fallback(self):
        fallback = Mock()
        request = self._request(cookie_value=str(self.session.session_key), from_formplayer=False)
        self._decorated_view(fallback=fallback)(request, self.webform.domain)
        fallback.assert_not_called()

    def test_no_usable_session_goes_to_the_fallback(self):
        fallback = Mock()
        request = self._request(cookie_value=str(uuid4()))
        response = self._decorated_view(fallback=fallback)(request, self.webform.domain)
        fallback.assert_called_once_with(request, self.webform.domain)
        assert response is fallback.return_value

    def test_no_header_leaves_couch_user_untouched(self):
        request = self._request(
            with_header=False, cookie_value=str(self.session.session_key))
        self._decorated_view()(request, self.webform.domain)
        assert request.couch_user is self.existing_user

    def test_no_cookie_leaves_couch_user_untouched(self):
        request = self._request(cookie_value=None)
        self._decorated_view()(request, self.webform.domain)
        assert request.couch_user is self.existing_user

    def test_invalid_cookie_leaves_couch_user_untouched(self):
        request = self._request(cookie_value='not-a-uuid')
        self._decorated_view()(request, self.webform.domain)
        assert request.couch_user is self.existing_user

    def test_unknown_key_leaves_couch_user_untouched(self):
        request = self._request(cookie_value=str(uuid4()))
        self._decorated_view()(request, self.webform.domain)
        assert request.couch_user is self.existing_user

    def test_expired_session_leaves_couch_user_untouched(self):
        self.session.expires_at = datetime.datetime(2000, 1, 1)
        self.session.save()
        request = self._request(cookie_value=str(self.session.session_key))
        self._decorated_view()(request, self.webform.domain)
        assert request.couch_user is self.existing_user

    def test_submitted_session_leaves_couch_user_untouched(self):
        self.session.submitted_at = datetime.datetime(2020, 1, 1)
        self.session.save()
        request = self._request(cookie_value=str(self.session.session_key))
        self._decorated_view()(request, self.webform.domain)
        assert request.couch_user is self.existing_user

    def test_public_webforms_not_enabled_leaves_couch_user_untouched(self):
        request = self._request(cookie_value=str(self.session.session_key))
        with patch(
            'corehq.apps.public_webforms.decorators.public_webforms_enabled',
            new=lambda domain: False,
        ):
            self._decorated_view()(request, self.webform.domain)
        assert request.couch_user is self.existing_user

    def test_a_different_domain_leaves_couch_user_untouched(self):
        request = self._request(cookie_value=str(self.session.session_key))
        self._decorated_view()(request, f'not-{self.webform.domain}')
        assert request.couch_user is self.existing_user
