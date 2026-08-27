import datetime
from uuid import uuid4

import pytest
from unmagic import use

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from casexml.apps.phone.xml import get_registration_element_data
from dimagi.utils.web import get_url_base

from corehq.apps.public_webforms.decorators import (
    PUBLIC_FORM_SESSION_COOKIE_NAME,
    PUBLIC_FORM_SESSION_HEADER,
    allow_public_form_session,
)
from corehq.apps.public_webforms.models import (
    OTARestorePublicFormUser,
    PublicFormSession,
    PublicFormUser,
    PublicWebform,
    PublicWebformStatus,
)
from corehq.apps.public_webforms.tests.utils import create_session, create_webform
from corehq.apps.users.util import PUBLIC_USER_ID


def test_public_url_is_absolute_and_keyed_on_the_public_id():
    webform = PublicWebform(public_id=uuid4())
    # absolute because it is shared over email, SMS, and QR code
    assert webform.public_url.startswith(get_url_base())
    assert webform.public_id.hex in webform.public_url


@pytest.mark.parametrize('offset, expected', [
    (datetime.timedelta(minutes=-1), True),
    (datetime.timedelta(minutes=1), False),
], ids=['past', 'future'])
def test_is_expired(offset, expected):
    assert PublicWebform(expires_at=timezone.now() + offset).is_expired is expected


@use('db')
@pytest.mark.parametrize('expires_in, is_disabled, expected', [
    (datetime.timedelta(days=1), False, PublicWebformStatus.OPEN),
    (datetime.timedelta(days=1), True, PublicWebformStatus.CLOSED),
    (datetime.timedelta(days=-1), False, PublicWebformStatus.EXPIRED),
    (datetime.timedelta(days=-1), True, PublicWebformStatus.EXPIRED),
], ids=['open', 'closed', 'expired', 'expired-and-closed'])
def test_with_status_derives_status_from_expiry_and_the_open_setting(
    expires_in, is_disabled, expected
):
    webform = create_webform(
        expires_at=timezone.now() + expires_in, is_disabled=is_disabled)

    annotated = PublicWebform.objects.with_status().get(pk=webform.pk)

    assert annotated.status == expected


@use('db')
@pytest.mark.parametrize('submitted_at, expected_submissions', [
    (None, 0),
    (timezone.now(), 1),
], ids=['no-submissions', 'one-submission'])
def test_with_submissions_count(submitted_at, expected_submissions):
    webform = create_webform()
    create_session(webform, submitted_at=submitted_at)

    annotated = PublicWebform.objects.with_submissions_count().get(pk=webform.pk)
    assert annotated.submissions == expected_submissions


@use('db')
def test_get_active_session_for_contact():
    webform = create_webform()
    session = create_session(webform, email='respondent@example.com')

    found = PublicFormSession.get_active_session_for_contact(
        webform, email='respondent@example.com', phone_number='')

    assert found == session


@use('db')
@pytest.mark.parametrize('session_kwargs', [
    {'expires_at': timezone.now() - datetime.timedelta(minutes=1)},
    {'submitted_at': timezone.now()},
], ids=['expired', 'already-submitted'])
def test_get_active_session_for_contact_ignores_inactive_session(session_kwargs):
    webform = create_webform()
    create_session(webform, email='respondent@example.com', **session_kwargs)

    assert PublicFormSession.get_active_session_for_contact(
        webform, email='respondent@example.com', phone_number='') is None


@pytest.mark.parametrize('email, phone_number', [
    ('respondent@example.com', '15551234567'),
    ('', ''),
], ids=['both', 'neither'])
def test_get_active_session_for_contact_requires_exactly_one_channel(email, phone_number):
    with pytest.raises(AssertionError):
        PublicFormSession.get_active_session_for_contact(
            PublicWebform(), email=email, phone_number=phone_number)


def test_public_form_session_username():
    webform = PublicWebform(domain='public-forms-domain')
    session = PublicFormSession(public_webform=webform)
    assert session.session_username == (
        f'{PUBLIC_USER_ID}{session.id.hex}@public-forms-domain.commcarehq.org'
    )


class PublicFormUserTests(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.domain = 'public-forms-domain'
        webform = PublicWebform(domain=self.domain)
        self.session = PublicFormSession(public_webform=webform)

    def test_user_id_is_shared_public_user_id(self):
        user = PublicFormUser(self.session)
        assert user.user_id == PUBLIC_USER_ID
        assert user.get_id == user.user_id

    def test_username_is_per_session(self):
        user = PublicFormUser(self.session)
        assert user.username == self.session.session_username
        assert user.raw_username == user.username
        assert self.session.id.hex in user.username

    def test_auth_status(self):
        user = PublicFormUser(self.session)
        assert user.is_authenticated is True
        assert user.is_web_user() is False
        assert user.is_commcare_user() is False

    def test_get_domains(self):
        user = PublicFormUser(self.session)
        assert user.get_domains() == [self.domain]

    def test_session_accessor_returns_underlying_session(self):
        user = PublicFormUser(self.session)
        assert user.session is self.session

    def test_can_access_mobile_endpoints_in_own_domain(self):
        user = PublicFormUser(self.session)
        assert user.has_permission(self.domain, 'access_mobile_endpoints') is True

    def test_cannot_access_mobile_endpoints_in_other_domain(self):
        user = PublicFormUser(self.session)
        assert user.has_permission('other-domain', 'access_mobile_endpoints') is False

    def test_has_no_other_permission(self):
        user = PublicFormUser(self.session)
        assert user.has_permission(self.domain, 'edit_data') is False

    def test_to_ota_restore_user(self):
        restore_user = PublicFormUser(self.session).to_ota_restore_user(self.domain)
        assert isinstance(restore_user, OTARestorePublicFormUser)


class OTARestorePublicFormUserTests(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.domain = 'public-forms-domain'
        webform = PublicWebform(domain=self.domain)
        self.session = PublicFormSession(public_webform=webform)
        self.session.created_at = datetime.datetime(2026, 7, 1)
        self.restore_user = OTARestorePublicFormUser(
            self.domain, PublicFormUser(self.session)
        )

    def test_requires_public_form_user(self):
        with pytest.raises(AssertionError):
            OTARestorePublicFormUser(self.domain, object())

    def test_restore_identity(self):
        assert self.restore_user.user_id == PUBLIC_USER_ID
        assert self.restore_user.username == self.session.session_username
        assert self.restore_user.full_username == self.session.session_username

    def test_registration_block_attributes_form_to_public_user_id(self):
        # The registration block's uuid is what formplayer stamps into every
        # submitted form's <meta><userID>, so this is where attribution is set.
        data = get_registration_element_data(self.restore_user)
        assert data['uuid'] == PUBLIC_USER_ID
        assert data['username'] == self.session.session_username

    def test_registration_block_fields(self):
        assert self.restore_user.password == ''
        assert self.restore_user.user_session_data == {}
        assert self.restore_user.date_joined == self.session.created_at

    def test_no_owner_ids(self):
        assert self.restore_user.get_owner_ids() == []

    def test_no_locations(self):
        assert self.restore_user.get_location_ids(self.domain) == []
        assert list(self.restore_user.get_sql_locations(self.domain)) == []
        assert self.restore_user.sql_location is None

    def test_no_role(self):
        assert self.restore_user.get_role(self.domain) is None

    def test_no_case_sharing_groups(self):
        assert self.restore_user.get_case_sharing_groups() == []

    def test_no_fixtures(self):
        assert self.restore_user.get_fixture_data_items() == []

    def test_no_commtrack_location(self):
        assert self.restore_user.get_commtrack_location_id() is None

    def test_no_call_center_indicators(self):
        assert self.restore_user.get_call_center_indicators(None) is None


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

    def _request(self, with_header=True, cookie_value=None):
        headers = {PUBLIC_FORM_SESSION_HEADER: 'true'} if with_header else {}
        request = self.factory.post('/a/public-forms-domain/receiver/', headers=headers)
        request.couch_user = self.existing_user
        if cookie_value is not None:
            request.COOKIES[PUBLIC_FORM_SESSION_COOKIE_NAME] = cookie_value
        return request

    @staticmethod
    def _decorated_view():
        @allow_public_form_session
        def view(request):
            return HttpResponse('ok')
        return view

    def test_valid_header_and_cookie_sets_public_form_user(self):
        request = self._request(cookie_value=str(self.session.session_key))
        self._decorated_view()(request)
        assert isinstance(request.couch_user, PublicFormUser)
        assert request.couch_user.user_id == PUBLIC_USER_ID

    def test_no_header_leaves_couch_user_untouched(self):
        request = self._request(
            with_header=False, cookie_value=str(self.session.session_key))
        self._decorated_view()(request)
        assert request.couch_user is self.existing_user

    def test_no_cookie_leaves_couch_user_untouched(self):
        request = self._request(cookie_value=None)
        self._decorated_view()(request)
        assert request.couch_user is self.existing_user

    def test_invalid_cookie_leaves_couch_user_untouched(self):
        request = self._request(cookie_value='not-a-uuid')
        self._decorated_view()(request)
        assert request.couch_user is self.existing_user

    def test_unknown_key_leaves_couch_user_untouched(self):
        request = self._request(cookie_value=str(uuid4()))
        self._decorated_view()(request)
        assert request.couch_user is self.existing_user

    def test_expired_session_leaves_couch_user_untouched(self):
        self.session.expires_at = datetime.datetime(2000, 1, 1)
        self.session.save()
        request = self._request(cookie_value=str(self.session.session_key))
        self._decorated_view()(request)
        assert request.couch_user is self.existing_user

    def test_submitted_session_leaves_couch_user_untouched(self):
        self.session.submitted_at = datetime.datetime(2020, 1, 1)
        self.session.save()
        request = self._request(cookie_value=str(self.session.session_key))
        self._decorated_view()(request)
        assert request.couch_user is self.existing_user
