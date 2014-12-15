from .models import (Message, METHOD_SMS, METHOD_SMS_CALLBACK, 
    METHOD_SMS_SURVEY, METHOD_IVR_SURVEY, METHOD_EMAIL, 
    RECIPIENT_USER, RECIPIENT_CASE, RECIPIENT_SURVEY_SAMPLE, CaseReminder,
    CaseReminderHandler)
from corehq.apps.smsforms.app import submit_unfinished_form
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.sms.mixin import (VerifiedNumber, apply_leniency,
    CommCareMobileContactMixin, InvalidFormatException)
from touchforms.formplayer.api import current_question
from corehq.apps.sms.api import (
    send_sms, send_sms_to_verified_number, MessageMetadata
)
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.util import form_requires_input
from corehq.apps.sms.util import format_message_list
from corehq.apps.users.models import CouchUser
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import (
    CallLog, ExpectedCallbackEventLog, CALLBACK_PENDING, CALLBACK_RECEIVED,
    CALLBACK_MISSED, WORKFLOW_REMINDER, WORKFLOW_KEYWORD, WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK,
)
from django.conf import settings
from corehq.apps.app_manager.models import Form
from corehq.apps.ivr.tasks import initiate_outbound_call
from datetime import timedelta
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.couch import CriticalSection
from django.utils.translation import ugettext as _, ugettext_noop
from casexml.apps.case.models import CommCareCase
from dimagi.utils.modules import to_function

ERROR_RENDERING_MESSAGE = ugettext_noop("Error rendering templated message for language '%s'. Please check message syntax.")
ERROR_NO_VERIFIED_NUMBER = ugettext_noop("Recipient has no phone number.")
ERROR_NO_OTHER_NUMBERS = ugettext_noop("Recipient has no phone number.")
ERROR_FORM = ugettext_noop("Can't load form. Please check configuration.")
ERROR_NO_RECIPIENTS = ugettext_noop("No recipient(s).")
ERROR_FINDING_CUSTOM_CONTENT_HANDLER = ugettext_noop("Error looking up custom content handler.")
ERROR_INVALID_CUSTOM_CONTENT_HANDLER = ugettext_noop("Invalid custom content handler.")


"""
This module defines the methods that will be called from CaseReminderHandler.fire()
when a reminder event fires.

Each method accepts the following parameters:
    reminder            The CaseReminder which is being fired. Use reminder.current_event
                        to see the specific event which is being fired.
                        
    handler             The CaseReminderHandler which defines the rules / schedule for
                        the reminder.
                        
    recipients          A list of recipients to send the content to. At the moment, this
                        will be list of CommCareUsers or CommCareCases.
                        
    verified_numbers    A dictionary of recipient.get_id : <first non-pending verified number>
                        If the recipient doesn't have a verified VerifiedNumber entry, None is the 
                        corresponding value.

Any changes to the reminder object made by the event handler method will be saved
after the method returns.

Each method should return True to move the reminder forward to the next event, or False
to not move the reminder forward to the next event. 

"""

def get_workflow(handler):
    from corehq.apps.reminders.models import REMINDER_TYPE_ONE_TIME, REMINDER_TYPE_KEYWORD_INITIATED
    if handler.reminder_type == REMINDER_TYPE_ONE_TIME:
        return WORKFLOW_BROADCAST
    elif handler.reminder_type == REMINDER_TYPE_KEYWORD_INITIATED:
        return WORKFLOW_KEYWORD
    else:
        return WORKFLOW_REMINDER


def get_recipient_phone_number(reminder, recipient, verified_numbers):
    verified_number = verified_numbers.get(recipient.get_id, None)
    unverified_number = None

    if verified_number is None:
        if isinstance(recipient, CouchUser):
            try:
                unverified_number = recipient.phone_number
            except Exception:
                unverified_number = None
        elif isinstance(recipient, CommCareCase):
            unverified_number = recipient.get_case_property("contact_phone_number")
            unverified_number = apply_leniency(unverified_number)
            if unverified_number:
                try:
                    CommCareMobileContactMixin.validate_number_format(
                        unverified_number)
                except InvalidFormatException:
                    unverified_number = None
            else:
                unverified_number = None

    return (verified_number, unverified_number)


def get_message_template_params(case):
    """
    Data such as case properties can be referenced from reminder messages
    such as {case.name} which references the case's name. Add to this result
    all data that can be referenced from a reminder message.

    The result is a dictionary where each key is the object's name and each
    value is a dictionary of attributes to be referenced. Dictionaries can
    also be nested, so a result here of {"case": {"parent": {"name": "joe"}}}
    allows you to reference {case.parent.name} in a reminder message.

    At the moment, the result here is of this structure:
    {
        "case": {
            ...key:value case properties...
            "parent": {
                ...key:value parent case properties...
            }
        }
    }
    """
    result = {"case": {}}
    if case:
        result["case"] = case.case_properties()

    parent_case = case.parent if case else None
    result["case"]["parent"] = {}
    if parent_case:
        result["case"]["parent"] = parent_case.case_properties()
    return result


def fire_sms_event(reminder, handler, recipients, verified_numbers, workflow=None):
    metadata = MessageMetadata(
        workflow=workflow or get_workflow(handler),
        reminder_id=reminder._id,
    )
    current_event = reminder.current_event
    case = reminder.case
    template_params = get_message_template_params(case)
    for recipient in recipients:
        try:
            lang = recipient.get_language_code()
        except Exception:
            lang = None

        if handler.custom_content_handler is not None:
            if handler.custom_content_handler in settings.ALLOWED_CUSTOM_CONTENT_HANDLERS:
                try:
                    content_handler = to_function(settings.ALLOWED_CUSTOM_CONTENT_HANDLERS[handler.custom_content_handler])
                except Exception:
                    raise_error(reminder, ERROR_FINDING_CUSTOM_CONTENT_HANDLER)
                    return False
                message = content_handler(reminder, handler, recipient)
                # If the content handler returns None or empty string,
                # don't send anything
                if not message:
                    return True
            else:
                raise_error(reminder, ERROR_INVALID_CUSTOM_CONTENT_HANDLER)
                return False
        else:
            message = current_event.message.get(lang, current_event.message[handler.default_lang])
            try:
                message = Message.render(message, **template_params)
            except Exception:
                if len(recipients) == 1:
                    raise_error(reminder, ERROR_RENDERING_MESSAGE % lang)
                    return False
                else:
                    raise_warning() # ERROR_RENDERING_MESSAGE
                    continue

        verified_number, unverified_number = get_recipient_phone_number(
            reminder, recipient, verified_numbers)

        domain_obj = Domain.get_by_name(reminder.domain, strict=True)
        if verified_number is not None:
            result = send_sms_to_verified_number(verified_number,
                message, metadata)
        elif isinstance(recipient, CouchUser) and unverified_number:
            result = send_sms(reminder.domain, recipient, unverified_number,
                message, metadata)
        elif (isinstance(recipient, CommCareCase) and unverified_number and
            domain_obj.send_to_duplicated_case_numbers):
            result = send_sms(reminder.domain, recipient, unverified_number,
                message, metadata)
        else:
            if len(recipients) == 1:
                raise_error(reminder, ERROR_NO_VERIFIED_NUMBER)
            result = False

        if len(recipients) == 1:
            return result

    # For multiple recipients, always move to the next event
    return True


def fire_sms_callback_event(reminder, handler, recipients, verified_numbers):
    current_event = reminder.current_event

    for recipient in recipients:
        send_message = False
        if reminder.callback_try_count > 0:
            if reminder.event_initiation_timestamp:
                event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                    key=[reminder.domain,
                         json_format_datetime(reminder.event_initiation_timestamp),
                         recipient.get_id],
                    include_docs=True,
                    limit=1).one()
                if not event:
                    continue
                if event.status == CALLBACK_RECEIVED:
                    continue
                if CallLog.inbound_entry_exists(recipient.doc_type,
                    recipient.get_id, reminder.event_initiation_timestamp):
                    event.status = CALLBACK_RECEIVED
                    event.save()
                    continue
            else:
                continue

            if (reminder.callback_try_count >=
                len(current_event.callback_timeout_intervals)):
                # On the last callback timeout, instead of sending the SMS
                # again, log the missed callback
                if event:
                    event.status = CALLBACK_MISSED
                    event.save()
            else:
                send_message = True
        else:
            # It's the first time sending the sms, so create an expected
            # callback event
            send_message = True
            event = ExpectedCallbackEventLog(
                domain=reminder.domain,
                date=reminder.event_initiation_timestamp,
                couch_recipient_doc_type=recipient.doc_type,
                couch_recipient=recipient.get_id,
                status=CALLBACK_PENDING,
            )
            event.save()

        if send_message:
            fire_sms_event(reminder, handler, [recipient], verified_numbers,
                workflow=WORKFLOW_CALLBACK)

    return True


def fire_sms_survey_event(reminder, handler, recipients, verified_numbers):
    if reminder.callback_try_count > 0:
        # Handle timeouts
        if handler.submit_partial_forms and (reminder.callback_try_count == len(reminder.current_event.callback_timeout_intervals)):
            # Submit partial form completions
            for session_id in reminder.xforms_session_ids:
                submit_unfinished_form(session_id, handler.include_case_side_effects)
        else:
            # Resend current question
            for session_id in reminder.xforms_session_ids:
                session = XFormsSession.by_session_id(session_id)
                if session.end_time is None:
                    vn = VerifiedNumber.view("sms/verified_number_by_owner_id",
                                             key=session.connection_id,
                                             include_docs=True).first()
                    if vn is not None:
                        metadata = MessageMetadata(
                            workflow=get_workflow(handler),
                            reminder_id=reminder._id,
                            xforms_session_couch_id=session._id,
                        )
                        resp = current_question(session_id)
                        send_sms_to_verified_number(vn, resp.event.text_prompt, metadata)
        return True
    else:
        reminder.xforms_session_ids = []

        # Get the app, module, and form
        try:
            form_unique_id = reminder.current_event.form_unique_id
            form = Form.get_form(form_unique_id)
            app = form.get_app()
            module = form.get_module()
        except Exception as e:
            raise_error(reminder, ERROR_FORM)
            return False

        # Start a touchforms session for each recipient
        for recipient in recipients:

            verified_number, unverified_number = get_recipient_phone_number(
                reminder, recipient, verified_numbers)

            domain_obj = Domain.get_by_name(reminder.domain, strict=True)
            no_verified_number = verified_number is None
            cant_use_unverified_number = (unverified_number is None or
                not domain_obj.send_to_duplicated_case_numbers or
                form_requires_input(form))
            if no_verified_number and cant_use_unverified_number:
                if len(recipients) == 1:
                    raise_error(reminder, ERROR_NO_VERIFIED_NUMBER)
                    return False
                else:
                    continue

            key = "start-sms-survey-for-contact-%s" % recipient.get_id
            with CriticalSection([key], timeout=60):
                # Close all currently open sessions
                XFormsSession.close_all_open_sms_sessions(reminder.domain,
                    recipient.get_id)

                # Start the new session
                if (isinstance(recipient, CommCareCase) and
                    not handler.force_surveys_to_use_triggered_case):
                    case_id = recipient.get_id
                else:
                    case_id = reminder.case_id
                session, responses = start_session(reminder.domain, recipient,
                    app, module, form, case_id, case_for_case_submission=
                    handler.force_surveys_to_use_triggered_case)
                session.survey_incentive = handler.survey_incentive
                session.workflow = get_workflow(handler)
                session.reminder_id = reminder._id
                session.save()

            reminder.xforms_session_ids.append(session.session_id)

            # Send out first message
            if len(responses) > 0:
                message = format_message_list(responses)
                metadata = MessageMetadata(
                    workflow=get_workflow(handler),
                    reminder_id=reminder._id,
                    xforms_session_couch_id=session._id,
                )
                if verified_number:
                    result = send_sms_to_verified_number(verified_number, message, metadata)
                else:
                    result = send_sms(reminder.domain, recipient, unverified_number,
                        message, metadata)

                if len(recipients) == 1:
                    return result

        return True

def fire_ivr_survey_event(reminder, handler, recipients, verified_numbers):
    domain_obj = Domain.get_by_name(reminder.domain, strict=True)
    for recipient in recipients:
        initiate_call = True
        if reminder.callback_try_count > 0 and reminder.event_initiation_timestamp:
            initiate_call = not CallLog.answered_call_exists(
                recipient.doc_type, recipient.get_id,
                reminder.event_initiation_timestamp,
                CaseReminderHandler.get_now())

        if initiate_call:
            if (isinstance(recipient, CommCareCase) and
                not handler.force_surveys_to_use_triggered_case):
                case_id = recipient.get_id
            else:
                case_id = reminder.case_id
            verified_number, unverified_number = get_recipient_phone_number(
                reminder, recipient, verified_numbers)
            if verified_number:
                initiate_outbound_call.delay(
                    recipient,
                    reminder.current_event.form_unique_id,
                    handler.submit_partial_forms,
                    handler.include_case_side_effects,
                    handler.max_question_retries,
                    verified_number=verified_number,
                    case_id=case_id,
                    case_for_case_submission=handler.force_surveys_to_use_triggered_case,
                    timestamp=CaseReminderHandler.get_now(),
                )
            elif domain_obj.send_to_duplicated_case_numbers and unverified_number:
                initiate_outbound_call.delay(
                    recipient,
                    reminder.current_event.form_unique_id,
                    handler.submit_partial_forms,
                    handler.include_case_side_effects,
                    handler.max_question_retries,
                    unverified_number=unverified_number,
                    case_id=case_id,
                    case_for_case_submission=handler.force_surveys_to_use_triggered_case,
                    timestamp=CaseReminderHandler.get_now(),
                )
            else:
                #No phone number to send to
                pass

    return True


def raise_warning():
    """
    This method is meant to report runtime warnings which are caused by
    configuration errors to a project contact.
    """
    # For now, just a stub.
    pass


def raise_error(reminder, error_msg):
    """
    Put the reminder in an error state, which filters it out of the reminders
    queue.
    """
    reminder.error = True
    reminder.error_msg = error_msg
    reminder.save()

# The dictionary which maps an event type to its event handling method

EVENT_HANDLER_MAP = {
    METHOD_SMS : fire_sms_event,
    METHOD_SMS_CALLBACK : fire_sms_callback_event,
    METHOD_SMS_SURVEY : fire_sms_survey_event,
    METHOD_IVR_SURVEY : fire_ivr_survey_event,
    # METHOD_EMAIL is a placeholder at the moment; it's not implemented yet anywhere in the framework
}



