from __future__ import absolute_import
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.smsforms.util import critical_section_for_smsforms_sessions
from corehq.messaging.scheduling.util import utcnow
from corehq.util.celery_utils import no_result_task


@no_result_task(queue='reminder_queue')
def handle_due_survey_action(domain, contact_id, session_id):
    with critical_section_for_smsforms_sessions(contact_id):
        session = SQLXFormsSession.by_session_id(session_id)
        if (
            not session
            or not session.session_is_open
            or session.current_action_due > utcnow()
        ):
            return

        if session.current_action_is_a_reminder:
            # Resend the current survey question to the contact
            session.move_to_next_action()
            session.save()
        else:
            # End the session
            pass
