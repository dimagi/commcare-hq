import logging

from django.utils import timezone

from casexml.apps.case.xform import get_case_updates

from corehq.apps.app_manager.models import PublicFormSession, PublicWebformTypes
from corehq.apps.users.util import PUBLIC_USER_ID
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.utils.xform import extract_meta_user_id
from corehq.util.metrics import metrics_counter

logger = logging.getLogger(__name__)


def validate_public_form_submission(session, form_json):
    """
    Structural gate for a public form submission, run before the form is
    persisted. Returns an error message if the submission is not allowed for
    the session's webform type, else ``None``.

    - Every submission must be attributed to PUBLIC_USER_ID.
    - Survey webforms may not submit any case data.
    - Registration webforms may only create new cases with PUBLIC_USER_ID.
    """
    if extract_meta_user_id(form_json) != PUBLIC_USER_ID:
        return f"Public form submissions must be attributed to '{PUBLIC_USER_ID}'."

    session_type = session.public_webform.session_type
    case_updates = get_case_updates(form_json)

    if session_type == PublicWebformTypes.SURVEY:
        if case_updates:
            return "Survey public forms may not submit case data."
        return None

    if session_type == PublicWebformTypes.REGISTRATION:
        return _validate_registration_case_updates(session, case_updates)

    return f"Unsupported public webform session type: {session_type}"


def _validate_registration_case_updates(session, case_updates):
    for case_update in case_updates:
        create_action = case_update.get_create_action()
        if create_action is None:
            # No create action means the block targets an existing case.
            return "Registration public forms may only create new cases."
        if create_action.owner_id != PUBLIC_USER_ID:
            return f"Registration public form cases must be owned by '{PUBLIC_USER_ID}'."
        update_action = case_update.get_update_action()
        if update_action and update_action.owner_id and update_action.owner_id != PUBLIC_USER_ID:
            return "Registration public forms may not reassign case ownership."
        if case_update.get_index_action():
            return "Registration public forms may not index cases."

    domain = session.public_webform.domain
    case_ids = [case_update.id for case_update in case_updates]
    if case_ids and CommCareCase.objects.get_case_ids_that_exist(domain, case_ids):
        return "Registration public form may not reuse an existing case id."
    return None


def consume_public_form_session(session, xform):
    """
    On the first successful submission, mark the session used and record the
    resulting xform id.
    """
    consumed = PublicFormSession.objects.filter(
        pk=session.pk,
        submitted_at__isnull=True,
    ).update(submitted_at=timezone.now(), xform_id=xform.form_id)
    if not consumed:
        metrics_counter(
            'commcare.public_form.already_consumed',
            tags={'domain': session.public_webform.domain},
        )
    return bool(consumed)
