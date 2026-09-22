import datetime
import urllib.parse

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.public_webforms.decorators import (
    PUBLIC_FORM_SESSION_COOKIE_NAME,
    PUBLIC_FORM_SESSION_HEADER,
)
from corehq.apps.public_webforms.models import PublicFormSession, PublicWebform

SESSION_HEADER = 'HTTP_' + PUBLIC_FORM_SESSION_HEADER.upper().replace('-', '_')


@override_settings(DEBUG=False)
class PublicFormSessionRestoreTest(TestCase):

    domain = 'test-public-restore'
    other_domain = 'test-public-restore-other'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_domain(cls.domain)
        create_domain(cls.other_domain)
        cls.addClassCleanup(delete_all_domains)

    def _make_session(self, domain):
        webform = PublicWebform.objects.create(
            domain=domain,
            label='Antenatal visit',
            app_id='app',
            app_build_id='build',
            form_unique_id='form',
            endpoint_id='endpoint',
            session_type='survey',
            allow_sms=False,
            allow_email=True,
            expires_at=timezone.now() + datetime.timedelta(days=30),
        )
        return PublicFormSession.objects.create(
            public_webform=webform,
            expires_at=timezone.now() + datetime.timedelta(hours=1),
        )

    def _restore(self, domain, session=None):
        if session is not None:
            self.client.cookies[PUBLIC_FORM_SESSION_COOKIE_NAME] = str(session.session_key)
        params = urllib.parse.urlencode({'version': 2.0, 'device_id': 'WebAppsLogin'})
        return self.client.get(
            '{}?{}'.format(reverse('ota_restore', args=[domain]), params),
            **{SESSION_HEADER: 'true'},
        )

    def test_a_session_may_restore_its_own_domain(self):
        session = self._make_session(self.domain)

        response = self._restore(self.domain, session)

        assert response.status_code == 200, response.content

    def test_a_session_is_not_a_credential_for_another_domain(self):
        session = self._make_session(self.other_domain)

        response = self._restore(self.domain, session)

        assert response.status_code == 401

    def test_without_a_session_the_usual_credentials_are_required(self):
        response = self._restore(self.domain)

        # with no session, falls through to mobile_auth_or_formplayer, which
        # denies auth because we provided no other credentials
        assert response.status_code == 401
