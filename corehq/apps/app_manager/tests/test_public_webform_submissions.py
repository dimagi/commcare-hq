from uuid import uuid4

from unmagic import use

from casexml.apps.case.mock import CaseBlock, CaseFactory

from corehq.apps.app_manager.models import PublicFormSession, PublicWebform
from corehq.apps.app_manager.public_webform_submissions import (
    validate_public_form_submission,
)
from corehq.apps.users.util import PUBLIC_USER_ID
from corehq.form_processor.utils.xform import convert_xform_to_json

DOMAIN = 'public-webform-submissions'


def _form_json(*case_blocks):
    cases = ''.join(cb.as_text() for cb in case_blocks)
    return convert_xform_to_json(
        f'<data xmlns="http://example.com/public-form">{cases}</data>'
    )


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
        form_json = convert_xform_to_json(
            f'<data xmlns="http://example.com/public-form">{case_xml}</data>'
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
