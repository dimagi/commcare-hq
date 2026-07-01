import datetime

import pytest

from django.test import SimpleTestCase

from casexml.apps.phone.xml import get_registration_element_data
from corehq.apps.app_manager.models import (
    OTARestorePublicFormUser,
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
