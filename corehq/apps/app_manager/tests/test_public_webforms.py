from django.test import SimpleTestCase

from corehq.apps.app_manager.models import (
    PublicFormSession,
    PublicFormUser,
    PublicWebform,
)
from corehq.apps.users.util import PUBLIC_USER_ID


class PublicFormSessionTests(SimpleTestCase):

    def test_session_username(self):
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
