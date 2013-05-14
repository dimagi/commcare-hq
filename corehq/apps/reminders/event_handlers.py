from .models import Message, METHOD_SMS, METHOD_SMS_CALLBACK, METHOD_SMS_SURVEY, METHOD_IVR_SURVEY, METHOD_EMAIL, METHOD_TEST, METHOD_SMS_CALLBACK_TEST, RECIPIENT_USER, RECIPIENT_CASE, RECIPIENT_SURVEY_SAMPLE
from corehq.apps.smsforms.app import submit_unfinished_form
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.sms.mixin import VerifiedNumber
from touchforms.formplayer.api import current_question
from corehq.apps.sms.api import send_sms, send_sms_to_verified_number, close_open_sessions
from corehq.apps.smsforms.app import start_session
from corehq.apps.sms.util import format_message_list
from corehq.apps.users.models import CouchUser
from corehq.apps.sms.models import CallLog, ExpectedCallbackEventLog, CALLBACK_PENDING, CALLBACK_RECEIVED, CALLBACK_MISSED
from django.conf import settings
from corehq.apps.app_manager.models import Form
from corehq.apps.ivr.api import initiate_outbound_call
from datetime import timedelta
from dimagi.utils.parsing import json_format_datetime

DEFAULT_OUTBOUND_RETRY_INTERVAL = 5
DEFAULT_OUTBOUND_RETRIES = 2

ERROR_RENDERING_MESSAGE = "Error rendering templated message for language '%s'. Please check message syntax."
ERROR_NO_VERIFIED_NUMBER = "Recipient has no phone number."
ERROR_NO_OTHER_NUMBERS = "Recipient has no phone number."
ERROR_FORM = "Can't load form. Please check configuration."

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

def fire_sms_event(reminder, handler, recipients, verified_numbers):
    current_event = reminder.current_event
    if reminder.method in [METHOD_SMS, METHOD_SMS_CALLBACK]:
        for recipient in recipients:
            try:
                lang = recipient.get_language_code()
            except Exception:
                lang = None
            
            message = current_event.message.get(lang, current_event.message[handler.default_lang])
            try:
                message = Message.render(message, case=reminder.case.case_properties())
            except Exception:
                if len(recipients) == 1:
                    raise_error(reminder, ERROR_RENDERING_MESSAGE % lang)
                    return False
                else:
                    raise_warning() # ERROR_RENDERING_MESSAGE
                    continue
            
            verified_number = verified_numbers[recipient.get_id]
            if verified_number is not None:
                result = send_sms_to_verified_number(verified_number, message)
                if not result:
                    raise_warning() # Could not send SMS
            elif isinstance(recipient, CouchUser):
                # If there is no verified number, but the recipient is a CouchUser, still try to send it
                try:
                    phone_number = recipient.phone_number
                except Exception:
                    phone_number = None
                
                if phone_number is None:
                    result = False
                    if len(recipients) == 1:
                        raise_error(reminder, ERROR_NO_OTHER_NUMBERS)
                    else:
                        raise_warning() # ERROR_NO_OTHER_NUMBERS
                else:
                    result = send_sms(reminder.domain, recipient.get_id, phone_number, message)
                    if not result:
                        raise_warning() # Could not send SMS
            else:
                if len(recipients) == 1:
                    raise_error(reminder, ERROR_NO_VERIFIED_NUMBER)
                else:
                    raise_warning() # ERROR_NO_VERIFIED_NUMBER
                result = False
            
            if len(recipients) == 1:
                return result
        
        # For multiple recipients, always move to the next event
        return True
    
    elif reminder.method in [METHOD_TEST, METHOD_SMS_CALLBACK_TEST]:
        # Used for automated tests
        return True

def fire_sms_callback_event(reminder, handler, recipients, verified_numbers):
    current_event = reminder.current_event
    if handler.recipient in [RECIPIENT_CASE, RECIPIENT_USER]:
        # If there are no recipients, just move to the next reminder event
        if len(recipients) == 0:
            return True
        
        # If the callback has been received, skip sending the next timeout message
        if reminder.callback_try_count > 0:
            # Lookup the expected callback event
            if reminder.event_initiation_timestamp is None:
                event = None
            else:
                event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                                      key=[reminder.domain, json_format_datetime(reminder.event_initiation_timestamp), recipients[0].get_id],
                                                      include_docs=True,
                                                      limit=1).one()
            
            # NOTE: If last_fired is None, it means that the reminder fired for the first time on a timeout interval
            if reminder.last_fired is not None and CallLog.inbound_call_exists(recipients[0].doc_type, recipients[0].get_id, reminder.last_fired):
                reminder.skip_remaining_timeouts = True
                if event is not None:
                    event.status = CALLBACK_RECEIVED
                    event.save()
                return True
            elif reminder.callback_try_count >= len(current_event.callback_timeout_intervals):
                # On the last callback timeout, instead of sending the SMS again, log the missed callback
                if event is not None:
                    event.status = CALLBACK_MISSED
                    event.save()
                return True
        else:
            # It's the first time sending the sms, so create an expected callback event
            event = ExpectedCallbackEventLog(
                domain                   = reminder.domain,
                date                     = reminder.event_initiation_timestamp,
                couch_recipient_doc_type = recipients[0].doc_type,
                couch_recipient          = recipients[0].get_id,
                status                   = CALLBACK_PENDING,
            )
            event.save()
        
        return fire_sms_event(reminder, handler, recipients, verified_numbers)
    else:
        # TODO: Implement sms callback for RECIPIENT_OWNER and RECIPIENT_SURVEY_SAMPLE
        return False

def fire_sms_survey_event(reminder, handler, recipients, verified_numbers):
    if handler.recipient in [RECIPIENT_CASE, RECIPIENT_SURVEY_SAMPLE]:
        if reminder.callback_try_count > 0:
            # Handle timeouts
            if handler.submit_partial_forms and (reminder.callback_try_count == len(reminder.current_event.callback_timeout_intervals)):
                # Submit partial form completions
                for session_id in reminder.xforms_session_ids:
                    submit_unfinished_form(session_id, handler.include_case_side_effects)
            else:
                # Resend current question
                for session_id in reminder.xforms_session_ids:
                    session = XFormsSession.view("smsforms/sessions_by_touchforms_id",
                                                    startkey=[session_id],
                                                    endkey=[session_id, {}],
                                                    include_docs=True).one()
                    if session.end_time is None:
                        vn = VerifiedNumber.view("sms/verified_number_by_owner_id",
                                                  key=session.connection_id,
                                                  include_docs=True).one()
                        if vn is not None:
                            resp = current_question(session_id)
                            send_sms_to_verified_number(vn, resp.event.text_prompt)
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
                verified_number = verified_numbers[recipient.get_id]
                if verified_number is None:
                    if len(recipients) == 1:
                        raise_error(reminder, ERROR_NO_VERIFIED_NUMBER)
                        return False
                    else:
                        raise_warning() # ERROR_NO_VERIFIED_NUMBER
                        continue
                
                # Close all currently open sessions
                close_open_sessions(reminder.domain, recipient.get_id)
                
                # Start the new session
                session, responses = start_session(reminder.domain, recipient, app, module, form, recipient.get_id)
                session.survey_incentive = handler.survey_incentive
                session.save()
                reminder.xforms_session_ids.append(session.session_id)
                
                # Send out first message
                if len(responses) > 0:
                    message = format_message_list(responses)
                    result = send_sms_to_verified_number(verified_number, message)
                    if not result:
                        raise_warning() # Could not send SMS
                    
                    if len(recipients) == 1:
                        return result
                
            return True
    else:
        # TODO: Make sure the above flow works for RECIPIENT_USER and RECIPIENT_OWNER
       return False

def fire_ivr_survey_event(reminder, handler, recipients, verified_numbers):
    if handler.recipient == RECIPIENT_CASE:
        # If there are no recipients, just move to the next reminder event
        if len(recipients) == 0:
            return True
        
        # If last_fired is None, it means that the reminder fired for the first time on a timeout interval. So we can
        # skip the lookup for the answered call since no call went out yet.
        if reminder.last_fired is not None and reminder.callback_try_count > 0 and CallLog.answered_call_exists(recipients[0].doc_type, recipients[0].get_id, reminder.last_fired):
            reminder.skip_remaining_timeouts = True
            return True
        verified_number = verified_numbers[recipients[0].get_id]
        if verified_number is not None:
            if initiate_outbound_call(verified_number, reminder.current_event.form_unique_id, handler.submit_partial_forms, handler.include_case_side_effects, handler.max_question_retries):
                return True
            else:
                reminder.error_retry_count += 1
                if reminder.error_retry_count > getattr(settings, "IVR_OUTBOUND_RETRIES", DEFAULT_OUTBOUND_RETRIES):
                    return True
                else:
                    reminder.next_fire += timedelta(minutes=getattr(settings, "IVR_OUTBOUND_RETRY_INTERVAL", DEFAULT_OUTBOUND_RETRY_INTERVAL))
                    reminder.save()
                    return False
        else:
            raise_error(reminder, ERROR_NO_VERIFIED_NUMBER)
            return False
    else:
        # TODO: Implement ivr survey for RECIPIENT_USER, RECIPIENT_OWNER, and RECIPIENT_SURVEY_SAMPLE
        return False

"""
This method is meant to report runtime warnings which are caused by configuration errors to a project contact.
"""
def raise_warning():
    # For now, just a stub.
    pass

"""
Put the reminder in an error state, which filters it out of the reminders queue.
"""
def raise_error(reminder, error_msg):
    reminder.error = True
    reminder.error_msg = error_msg
    reminder.save()

# The dictionary which maps an event type to its event handling method

EVENT_HANDLER_MAP = {
    METHOD_SMS : fire_sms_event,
    METHOD_SMS_CALLBACK : fire_sms_callback_event,
    METHOD_SMS_SURVEY : fire_sms_survey_event,
    METHOD_IVR_SURVEY : fire_ivr_survey_event,
    METHOD_TEST : fire_sms_event,
    METHOD_SMS_CALLBACK_TEST : fire_sms_callback_event,
    # METHOD_EMAIL is a placeholder at the moment; it's not implemented yet anywhere in the framework
}



