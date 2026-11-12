import datetime
from types import SimpleNamespace
from uuid import uuid4

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from unmagic import fixture, use

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.ota.origin_token import ORIGIN_TOKEN_SLUG
from corehq.apps.public_webforms.models import PublicFormSession, PublicWebform
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.privileges import PUBLIC_WEBFORMS
from corehq.util.test_utils import flag_enabled, privilege_enabled

DOMAIN = 'public-forms-domain'
OTHER_DOMAIN = 'public-forms-other-domain'
PASSWORD = 'Passw0rd!'
ADMIN_USER = 'webform-admin@example.com'
NORMAL_USER = 'normal-user@example.com'


@fixture
def public_webforms_available():
    with flag_enabled('PUBLIC_WEBFORMS'), privilege_enabled(PUBLIC_WEBFORMS):
        yield


@fixture
def skip_turnstile():
    with override_settings(TURNSTILE_SECRET_KEY=''):
        yield


def create_webform(**kwargs):
    return PublicWebform.objects.create(**{
        'domain': DOMAIN,
        'label': 'Antenatal visit',
        'app_id': 'app',
        'app_build_id': 'build',
        'form_unique_id': 'form',
        'endpoint_id': 'endpoint',
        'session_type': 'survey',
        'allow_sms': False,
        'allow_email': True,
        'expires_at': timezone.now() + datetime.timedelta(days=30),
        **kwargs,
    })


def formplayer_origin_headers():
    """Headers that make a request pass ``is_from_formplayer``.

    Formplayer proves its origin to HQ with a per-request token: it stores
    ``OriginToken<token>`` in Redis for 60 seconds and sends the token in
    ``X-CommCareHQ-Origin-Token``. HQ accepts the header only if that key
    exists with the value ``"valid"``, quotes included, as formplayer JSON
    encodes it. This writes the same key so the real check passes.
    """
    token = uuid4().hex
    redis = get_redis_client().client.get_client()
    redis.set(f'{ORIGIN_TOKEN_SLUG}{token}', '"valid"', ex=60)
    return {'X-CommCareHQ-Origin-Token': token}


def create_session(webform, **kwargs):
    return PublicFormSession.objects.create(**{
        'public_webform': webform,
        'expires_at': timezone.now() + PublicFormSession.DEFAULT_LIFESPAN,
        **kwargs,
    })


@use('db')
@fixture
def saved_app():
    app = Application.new_app(DOMAIN, 'Antenatal')
    app.save()
    try:
        yield app
    finally:
        Application.get_db().delete_doc(app._id)


def build_app():
    """An app with one of each relevant form: an eligible survey form, an
    eligible registration form, an ineligible case-requiring form, and a form
    in an advanced (non-basic) menu."""
    factory = AppFactory(domain='pwf-test', name='Public Forms App', build_version='2.51.0')
    factory.app.copy_of = 'app-1'
    __, survey_form = factory.new_basic_module('survey', 'patient')
    __, registration_form = factory.new_basic_module('registration', 'patient')
    factory.form_opens_case(registration_form, 'patient')
    __, followup_form = factory.new_basic_module('followup', 'patient')
    factory.form_requires_case(followup_form)
    __, advanced_form = factory.new_advanced_module('advanced', 'patient')
    return SimpleNamespace(
        app=factory.app,
        domain=factory.app.domain,
        survey_form=survey_form,
        registration_form=registration_form,
        survey_form_id=survey_form.unique_id,
        registration_form_id=registration_form.unique_id,
        followup_form_id=followup_form.unique_id,
        advanced_form_id=advanced_form.unique_id,
    )


@use('db')
@fixture
def webform_domain():
    domain_obj = create_domain(DOMAIN)
    try:
        yield domain_obj
    finally:
        domain_obj.delete()


class PublicWebformViewTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for domain in (DOMAIN, OTHER_DOMAIN):
            domain_obj = create_domain(domain)
            cls.addClassCleanup(domain_obj.delete)
        cls.make_user(ADMIN_USER, HqPermissions(edit_public_webforms=True))
        cls.make_user(NORMAL_USER, HqPermissions())

    @classmethod
    def make_user(cls, username, permissions):
        role = UserRole.create(DOMAIN, username, permissions=permissions)
        user = WebUser.create(
            domain=DOMAIN,
            username=username,
            password=PASSWORD,
            role_id=role.get_id,
            created_by=None,
            created_via=None,
        )
        cls.addClassCleanup(user.delete, DOMAIN, deleted_by=None)
        return user

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.sign_in(ADMIN_USER)

    def sign_in(self, username):
        self.client.login(username=username, password=PASSWORD)
