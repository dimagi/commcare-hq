import datetime
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from unmagic import fixture, use

from casexml.apps.case.mock import CaseBlock, CaseFactory

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.app_manager.models import PublicFormSession, PublicWebform
from corehq.apps.app_manager.public_webform_submissions import (
    consume_public_form_session,
    public_form_session_already_submitted,
    validate_public_form_submission,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.util import PUBLIC_USER_ID
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.form_processor.utils.xform import convert_xform_to_json

DOMAIN = 'public-webform-submissions'


def _form_json(*case_blocks, user_id=PUBLIC_USER_ID):
    return convert_xform_to_json(_form_xml(*case_blocks, user_id=user_id))


def _form_xml(*case_blocks, user_id=PUBLIC_USER_ID):
    meta = (
        '<n0:meta xmlns:n0="http://openrosa.org/jr/xforms">'
        f'<n0:userID>{user_id}</n0:userID>'
        '</n0:meta>'
    ) if user_id is not None else ''
    cases = ''.join(cb.as_text() for cb in case_blocks)
    return f'<data xmlns="http://example.com/public-form">{meta}{cases}</data>'


def _create_block(owner_id=PUBLIC_USER_ID, case_id=None, **kwargs):
    return CaseBlock(
        case_id=case_id or uuid4().hex,
        create=True,
        owner_id=owner_id,
        case_type='patient',
        case_name='Test',
        **kwargs,
    )


def _session(session_type, domain=DOMAIN):
    """An in-memory session for validation, which reads only session_type and
    domain off the (unsaved) webform."""
    webform = PublicWebform(domain=domain, session_type=session_type)
    return PublicFormSession(public_webform=webform)


class _FakeXForm:
    def __init__(self, form_id):
        self.form_id = form_id


class TestValidateAttribution:
    # userID attribution is checked for every session type before any case
    # data, so a survey session is sufficient to exercise it.

    def test_wrong_user_id_is_rejected(self):
        session = _session('survey')
        assert validate_public_form_submission(
            session, _form_json(user_id='some-real-user')) is not None

    def test_missing_user_id_is_rejected(self):
        session = _session('survey')
        assert validate_public_form_submission(
            session, _form_json(user_id=None)) is not None


class TestValidateSurveySubmission:

    def test_survey_without_case_data_is_allowed(self):
        session = _session('survey')
        assert validate_public_form_submission(session, _form_json()) is None

    def test_survey_with_case_data_is_rejected(self):
        session = _session('survey')
        error = validate_public_form_submission(session, _form_json(_create_block()))
        assert error is not None


@use('db')
class TestValidateRegistrationSubmission:

    def test_create_owned_by_public_user_is_allowed(self):
        session = _session('registration')
        block = _create_block(update={'age': '30'})
        assert validate_public_form_submission(session, _form_json(block)) is None

    def test_create_with_wrong_owner_is_rejected(self):
        session = _session('registration')
        block = _create_block(owner_id='some-real-user')
        assert validate_public_form_submission(session, _form_json(block)) is not None

    def test_update_without_create_is_rejected(self):
        session = _session('registration')
        block = CaseBlock(case_id=uuid4().hex, update={'age': '30'})
        assert validate_public_form_submission(session, _form_json(block)) is not None

    def test_owner_reassignment_via_update_is_rejected(self):
        # A crafted submission that creates as the public owner but reassigns
        # ownership in the update block. CaseBlock refuses to build this, so
        # the XML is hand-written as a hostile client could send it.
        session = _session('registration')
        case_xml = (
            f'<case case_id="{uuid4().hex}" date_modified="2020-01-01T00:00:00.000000Z"'
            f' xmlns="http://commcarehq.org/case/transaction/v2">'
            f'<create><case_type>patient</case_type><case_name>Test</case_name>'
            f'<owner_id>{PUBLIC_USER_ID}</owner_id></create>'
            f'<update><owner_id>some-real-user</owner_id></update>'
            f'</case>'
        )
        meta = (
            '<n0:meta xmlns:n0="http://openrosa.org/jr/xforms">'
            f'<n0:userID>{PUBLIC_USER_ID}</n0:userID>'
            '</n0:meta>'
        )
        form_json = convert_xform_to_json(
            f'<data xmlns="http://example.com/public-form">{meta}{case_xml}</data>'
        )
        assert validate_public_form_submission(session, form_json) is not None

    def test_index_is_rejected(self):
        session = _session('registration')
        block = _create_block(index={'parent': ('patient', uuid4().hex)})
        assert validate_public_form_submission(session, _form_json(block)) is not None

    def test_reusing_existing_case_id_is_rejected(self):
        existing = CaseFactory(DOMAIN).create_case(owner_id=PUBLIC_USER_ID)
        session = _session('registration')
        block = _create_block(case_id=existing.case_id)
        assert validate_public_form_submission(session, _form_json(block)) is not None


@use('db')
@fixture
def consumable_session():
    future_expiration = datetime.datetime.today() + datetime.timedelta(days=30)
    webform = PublicWebform.objects.create(
        domain=DOMAIN,
        app_id='app',
        app_build_id='build',
        form_unique_id='form',
        endpoint_id='endpoint',
        session_type='survey',
        allow_sms=False,
        allow_email=True,
        expires_at=future_expiration,
    )
    yield PublicFormSession.objects.create(
        public_webform=webform,
        expires_at=future_expiration,
    )


@use(consumable_session)
class TestConsumePublicFormSession:

    def test_consume_sets_submitted_at_and_xform_id(self):
        session = consumable_session()
        assert consume_public_form_session(session, _FakeXForm('form-abc')) is True
        session.refresh_from_db()
        assert session.submitted_at is not None
        assert session.xform_id == 'form-abc'

    def test_second_consume_is_a_noop(self):
        session = consumable_session()
        assert consume_public_form_session(session, _FakeXForm('form-abc')) is True
        assert consume_public_form_session(session, _FakeXForm('form-xyz')) is False
        session.refresh_from_db()
        # still the first form; the replay did not overwrite
        assert session.xform_id == 'form-abc'


@use(consumable_session)
class TestPublicFormSessionAlreadySubmitted:

    def test_false_before_submission(self):
        assert public_form_session_already_submitted(consumable_session()) is False

    def test_true_after_submission(self):
        session = consumable_session()
        consume_public_form_session(session, _FakeXForm('form-abc'))
        assert public_form_session_already_submitted(session) is True


@use('transactional_db')
@fixture
def receiver_domain():
    """A domain with an active subscription, for driving the receiver end to end.

    Uses transactional_db (not db): the receiver writes the form to the sharded
    backend, whose proxy reads cannot see uncommitted changes, so a wrapping
    per-test transaction would hide the write. transactional_db truncates
    between tests instead of rolling back; the subscription setup here must
    re-bootstrap roles and default plans.
    """
    call_command('cchq_prbac_bootstrap')
    domain_obj = create_domain('public-receiver')
    subscription = DomainSubscriptionMixin()
    subscription.setup_subscription(domain_obj.name, SoftwarePlanEdition.ADVANCED)
    try:
        yield domain_obj
    finally:
        subscription.teardown_subscription(domain_obj.name)
        FormProcessorTestUtils.delete_all_xforms(domain_obj.name)
        domain_obj.delete()


@use(receiver_domain)
@fixture
def receiver_webform():
    """A survey webform on the receiver domain, for driving the receiver end to end."""
    yield PublicWebform.objects.create(
        domain=receiver_domain().name,
        app_id='app',
        app_build_id='build',
        form_unique_id='form',
        endpoint_id='endpoint',
        session_type='survey',
        allow_sms=False,
        allow_email=True,
        expires_at=datetime.datetime.today() + datetime.timedelta(days=30),
    )


@sharded
@use(receiver_webform)
class TestPublicFormReceiverIntegration:
    """End-to-end: a submission carrying the public session cookie + header is
    resolved to a PublicFormUser, validated pre-persist, and consumes the
    session on success."""

    def _session(self):
        return PublicFormSession.objects.create(
            public_webform=receiver_webform(), expires_at=datetime.datetime.today() + datetime.timedelta(days=30))

    def _submit(self, session, case_block_xml=''):
        form_xml = (
            '<?xml version="1.0" ?>'
            '<data xmlns="http://commcarehq.org/public-form-test">'
            '<name>test</name>'
            f'{case_block_xml}'
            '<n0:meta xmlns:n0="http://openrosa.org/jr/xforms">'
            f'<n0:instanceID>{uuid4().hex}</n0:instanceID>'
            f'<n0:userID>{PUBLIC_USER_ID}</n0:userID>'
            '</n0:meta>'
            '</data>'
        )
        client = Client()
        client.cookies['public_form_session_key'] = str(session.session_key)
        url = reverse('receiver_post', args=[receiver_webform().domain])
        return client.post(
            url,
            {'xml_submission_file': SimpleUploadedFile('form.xml', form_xml.encode('utf-8'))},
            headers={'CommCare-Public-Session': 'true'},
        )

    def test_survey_submission_accepted_and_consumes_session(self):
        session = self._session()
        response = self._submit(session)
        assert response.status_code == 201
        session.refresh_from_db()
        assert session.submitted_at is not None
        assert session.xform_id

    def test_survey_submission_with_case_data_is_rejected(self):
        session = self._session()
        case_xml = _create_block().as_text()
        response = self._submit(session, case_xml)
        assert response.status_code == 400
        session.refresh_from_db()
        assert session.submitted_at is None
