from datetime import timedelta

from dimagi.utils.logging import notify_error, notify_exception

from corehq import toggles
from corehq.apps.celery import task
from corehq.apps.formplayer_api.smsforms.api import (
    FormplayerInterface,
    TouchformsError,
)
from corehq.apps.sms.api import (
    MessageMetadata,
    send_sms,
    send_sms_to_verified_number,
)
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.sms.util import format_message_list
from corehq.apps.smsforms.app import (
    _responses_to_text,
    get_events_from_responses,
)
from corehq.apps.smsforms.models import (
    SQLXFormsSession,
    XFormsSessionSynchronization,
)
from corehq.apps.smsforms.util import critical_section_for_smsforms_sessions
from corehq.messaging.scheduling.util import utcnow
from corehq.util.celery_utils import no_result_task
from corehq.util.metrics import metrics_counter


@no_result_task(serializer='pickle', queue='background_queue')
def send_first_message(domain, recipient, phone_entry_or_number, session, responses, logged_subevent, workflow):
    # This try/except section is just here (temporarily) to support future refactors
    # If any of these notify, they should be replaced with a comment as to why the two are different
    # so that someone refactoring in the future will know that this or that param is necessary.
    try:
        if session.workflow != workflow:
            # see if we can eliminate the workflow arg
            notify_error('Exploratory: session.workflow != workflow', details={
                'session.workflow': session.workflow, 'workflow': workflow})
        if session.connection_id != recipient.get_id:
            # see if we can eliminate the recipient arg
            notify_error('Exploratory: session.connection_id != recipient.get_id', details={
                'session.connection_id': session.connection_id, 'recipient.get_id': recipient.get_id,
                'recipient': recipient
            })
        if session.related_subevent != logged_subevent:
            # see if we can eliminate the logged_subevent arg
            notify_error('Exploratory: session.related_subevent != logged_subevent', details={
                'session.connection_id': session.connection_id, 'logged_subevent': logged_subevent})
    except Exception:
        # The above running is not mission critical, so if it errors just leave a message in the log
        # for us to follow up on.
        # Absence of the message below and messages above ever notifying
        # will indicate that we can remove these args.
        notify_exception(None, "Error in section of code that's just supposed help inform future refactors")

    if toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(domain):
        if not XFormsSessionSynchronization.claim_channel_for_session(session):
            send_first_message.apply_async(
                args=(domain, recipient, phone_entry_or_number, session, responses, logged_subevent, workflow),
                countdown=60
            )
            return

    metrics_counter('commcare.smsforms.session_started', 1, tags={'domain': domain, 'workflow': workflow})

    if len(responses) > 0:
        text_responses = _responses_to_text(responses)
        message = format_message_list(text_responses)
        events = get_events_from_responses(responses)
        metadata = MessageMetadata(
            workflow=workflow,
            xforms_session_couch_id=session.couch_id,
            messaging_subevent_id=logged_subevent.pk
        )

        if isinstance(phone_entry_or_number, PhoneNumber):
            send_sms_to_verified_number(
                phone_entry_or_number,
                message,
                metadata,
                logged_subevent=logged_subevent,
                events=events
            )
        else:
            send_sms(
                domain,
                recipient,
                phone_entry_or_number,
                message,
                metadata
            )
    logged_subevent.completed()


@no_result_task(serializer='pickle', queue='reminder_queue')
def handle_due_survey_action(domain, contact_id, session_id):
    with critical_section_for_smsforms_sessions(contact_id):
        session = SQLXFormsSession.by_session_id(session_id)
        if (
            not session
            or not session.session_is_open
            or session.current_action_due > utcnow()
        ):
            return

        if toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(domain):
            if not XFormsSessionSynchronization.claim_channel_for_session(session):
                from .management.commands import handle_survey_actions

                # Unless we release this lock, handle_survey_actions will be unable to requeue this task
                # for the default duration of 1h, which we don't want
                handle_survey_actions.Command.get_enqueue_lock(session_id, session.current_action_due).release()
                return

        if session_is_stale(session):
            # If a session is having some unrecoverable errors that aren't benefitting from
            # being retried, those errors should show up in sentry log and the fix should
            # be dealt with. In terms of the current session itself, we just close it out
            # to allow new sessions to start.
            session.mark_completed(False)
            return

        if session.current_action_is_a_reminder:
            # Resend the current question in the open survey to the contact
            p = PhoneNumber.get_phone_number_for_owner(session.connection_id, session.phone_number)
            if p:
                subevent = session.related_subevent
                metadata = MessageMetadata(
                    workflow=session.workflow,
                    xforms_session_couch_id=session._id,
                    messaging_subevent_id=subevent.pk if subevent else None
                )
                resp = FormplayerInterface(session.session_id, domain).current_question()
                send_sms_to_verified_number(
                    p,
                    resp.event.text_prompt,
                    metadata,
                    logged_subevent=subevent
                )

            session.move_to_next_action()
            session.save()
        else:
            close_session.delay(contact_id, session_id)


@task(serializer='pickle', queue='reminder_queue', bind=True, max_retries=3, default_retry_delay=15 * 60)
def close_session(self, contact_id, session_id):
    with critical_section_for_smsforms_sessions(contact_id):
        session = SQLXFormsSession.by_session_id(session_id)
        try:
            session.close(force=False)
        except TouchformsError as e:
            try:
                self.retry(exc=e)
            except TouchformsError as e:
                raise e
            finally:
                # Eventually the session needs to get closed
                session.mark_completed(False)
                return


def session_is_stale(session):
    return utcnow() > (session.start_time + timedelta(minutes=SQLXFormsSession.MAX_SESSION_LENGTH * 2))
