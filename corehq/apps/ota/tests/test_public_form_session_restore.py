import datetime
import urllib.parse
from contextlib import ExitStack

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    delete_all_apps,
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.public_webforms.decorators import (
    PUBLIC_FORM_SESSION_COOKIE_NAME,
    PUBLIC_FORM_SESSION_HEADER,
)
from corehq.apps.public_webforms.models import PublicFormSession, PublicWebform
from corehq.form_processor.tests.utils import create_case
from corehq.util.test_utils import flag_enabled

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
        # without an app in the project, the fixture providers that filter by
        # app access return before ever reaching the user
        factory = AppFactory(cls.domain, name='Test App')
        __, form = factory.new_basic_module('survey', 'patient')
        form.source = get_simple_form(xmlns=form.unique_id)
        with patch_validate_xform():
            app = factory.app
            app.save()
            build = app.make_build()
            build.save()
        cls.addClassCleanup(delete_all_apps)
        cls.app_id = app.get_id
        cls.app_build_id = build.get_id

    def _make_session(self, domain):
        webform = PublicWebform.objects.create(
            domain=domain,
            label='Antenatal visit',
            app_id=self.app_id,
            app_build_id=self.app_build_id,
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

    def test_a_session_may_restore_with_domain_gated_fixtures(self):
        session = self._make_session(self.domain)

        # these providers reach past the restore user into its _couch_user, so
        # they only exercise the proxy on the projects that have them turned on
        for toggle_names in [
            ['CSQL_FIXTURE'],
            ['DATA_REGISTRY'],
            ['MOBILE_UCR'],
            ['MOBILE_UCR', 'RESTORE_ACCESSIBLE_REPORTS_ONLY'],
        ]:
            with self.subTest(' '.join(toggle_names)), ExitStack() as stack:
                for toggle_name in toggle_names:
                    stack.enter_context(flag_enabled(toggle_name))

                response = self._restore(self.domain, session)

                assert response.status_code == 200, response.content

    def test_a_session_restores_no_project_case_data(self):
        case = create_case(self.domain, case_type='patient', save=True)
        self.addCleanup(case.delete)
        session = self._make_session(self.domain)

        response = self._restore(self.domain, session)

        # an owner id the restore cannot filter on syncs the whole project
        payload = b''.join(response.streaming_content).decode()
        assert case.case_id not in payload
        assert '<case ' not in payload

    def test_a_session_restores_as_itself(self):
        session = self._make_session(self.domain)

        response = self._restore(self.domain, session)

        payload = b''.join(response.streaming_content).decode()
        assert session.session_username in payload

    def test_a_session_restores_the_build_its_link_is_pinned_to(self):
        session = self._make_session(self.domain)
        session.public_webform.app_build_id = 'not-a-build'
        session.public_webform.save()

        response = self._restore(self.domain, session)

        # the client cannot choose the app, so a link whose build is gone is dead
        assert response.status_code == 404

    def test_a_session_is_not_a_credential_for_another_domain(self):
        session = self._make_session(self.other_domain)

        response = self._restore(self.domain, session)

        assert response.status_code == 401

    def test_without_a_session_the_usual_credentials_are_required(self):
        response = self._restore(self.domain)

        # with no session, falls through to mobile_auth_or_formplayer, which
        # denies auth because we provided no other credentials
        assert response.status_code == 401
