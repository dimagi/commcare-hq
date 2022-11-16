from dimagi.utils.couch import CriticalSection
from corehq.apps.sms.models import SMS
from corehq.apps.receiverwrapper.util import submit_form_locally


def form_requires_input(form):
    """
    Returns True if the form has at least one question that requires input
    """
    for question in form.get_questions([]):
        if question["tag"] not in ("trigger", "label", "hidden"):
            return True

    return False


def process_sms_form_complete(session_id, form):
    from corehq.apps.smsforms.models import SQLXFormsSession
    session = SQLXFormsSession.by_session_id(session_id)
    if not session:
        return

    attachments = get_sms_form_incoming_media_files(session)
    result = submit_form_locally(
        form,
        session.domain,
        app_id=session.app_id,
        partial_submission=False,
        attachments=attachments
    )
    session.submission_id = result.xform.form_id
    session.mark_completed(True)


def get_sms_form_incoming_media_files(session):
    attachments = {}
    for message in SMS.objects.filter(xforms_session_couch_id=session._id):
        if message.custom_metadata and 'media_urls' in message.custom_metadata:
            media_urls = message.custom_metadata['media_urls']
            for media_url in media_urls:
                file_id, file = message.outbound_backend.download_incoming_media(media_url)
                attachments[file_id] = file
    return attachments


def critical_section_for_smsforms_sessions(contact_id):
    return CriticalSection(['smsforms-sessions-lock-for-contact-%s' % contact_id], timeout=5 * 60)
