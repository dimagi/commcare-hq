from __future__ import absolute_import
from corehq.apps.sms.api import send_sms_to_verified_number, MessageMetadata
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.smsforms.util import critical_section_for_smsforms_sessions
from corehq.messaging.scheduling.util import utcnow
from corehq.util.celery_utils import no_result_task
from touchforms.formplayer.api import current_question


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
            # Resend the current question in the open survey to the contact
            p = PhoneNumber.get_phone_number_for_owner(session.connection_id, session.phone_number)
            if p:
                metadata = MessageMetadata(
                    workflow=session.workflow,
                    xforms_session_couch_id=session._id,
                )
                resp = current_question(session.session_id)
                send_sms_to_verified_number(
                    p,
                    resp.event.text_prompt,
                    metadata,
                    logged_subevent=session.related_subevent
                )

            session.move_to_next_action()
            session.save()
        else:
            # Close the session
            session.close()
            session.save()
