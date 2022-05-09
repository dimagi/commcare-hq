from corehq.apps.smsforms.util import process_sms_form_complete


def handle_sms_form_complete(session_id, form):
    from corehq.apps.smsforms.models import SQLXFormsSession
    session = SQLXFormsSession.by_session_id(session_id)
    if session:
        process_sms_form_complete(session, form)
