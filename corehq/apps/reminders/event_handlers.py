from corehq.apps.accounting.utils import domain_is_on_trial
from corehq.apps.reminders.models import (Message, METHOD_SMS,
    METHOD_SMS_CALLBACK, METHOD_SMS_SURVEY, METHOD_IVR_SURVEY,
    METHOD_EMAIL, CaseReminderHandler, EmailUsage)
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.ivr.models import Call
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.util import get_unverified_number_for_recipient
from corehq.apps.smsforms.app import submit_unfinished_form
from corehq.apps.smsforms.models import get_session_by_session_id, SQLXFormsSession
from touchforms.formplayer.api import current_question, TouchformsError
from corehq.apps.sms.api import (
    send_sms, send_sms_to_verified_number, MessageMetadata
)
from corehq.apps.smsforms.app import start_session
from corehq.apps.smsforms.util import form_requires_input
from corehq.apps.sms.util import format_message_list, touchforms_error_is_config_error
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.users.models import CouchUser, WebUser, CommCareUser
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import (
    ExpectedCallback, CALLBACK_PENDING, CALLBACK_RECEIVED,
    CALLBACK_MISSED, WORKFLOW_REMINDER, WORKFLOW_KEYWORD, WORKFLOW_BROADCAST,
    WORKFLOW_CALLBACK, MessagingEvent,
)
from django.conf import settings
from corehq.apps.app_manager.models import Form
from corehq.apps.ivr.tasks import initiate_outbound_call
from corehq.form_processor.utils import is_commcarecase
from dimagi.utils.couch import CriticalSection
from django.utils.translation import ugettext_noop
from dimagi.utils.modules import to_function

TRIAL_MAX_EMAILS = 50
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
                        If the recipient doesn't have a verified PhoneNumber entry, None is the
                        corresponding value.

Any changes to the reminder object made by the event handler method will be saved
after the method returns.

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
        unverified_number = get_unverified_number_for_recipient(recipient)
    return (verified_number, unverified_number)


def _get_case_template_info(case):
    return case.to_json()


def _get_web_user_template_info(user):
    return {
        'name': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
    }


def _get_mobile_user_template_info(user):
    return {
        'name': user.raw_username,
        'first_name': user.first_name,
        'last_name': user.last_name,
    }


def _get_group_template_info(group):
    return {
        'name': group.name,
    }


def _get_location_template_info(location):
    return {
        'name': location.name,
        'site_code': location.site_code,
    }


def _get_obj_template_info(obj):
    if is_commcarecase(obj):
        return _get_case_template_info(obj)
    elif isinstance(obj, WebUser):
        return _get_web_user_template_info(obj)
    elif isinstance(obj, CommCareUser):
        return _get_mobile_user_template_info(obj)
    elif isinstance(obj, Group):
        return _get_group_template_info(obj)
    elif isinstance(obj, SQLLocation):
        return _get_location_template_info(obj)

    return {}


def _add_case_to_template_params(case, result):
    result['case'] = _get_obj_template_info(case)


def _add_parent_case_to_template_params(case, result):
    parent_case = case.parent
    if parent_case:
        result['case']['parent'] = _get_obj_template_info(parent_case)


def _add_owner_to_template_params(case, result):
    owner = get_wrapped_owner(get_owner_id(case))
    if owner:
        result['case']['owner'] = _get_obj_template_info(owner)


def _add_modified_by_to_template_params(case, result):
    try:
        modified_by = CouchUser.get_by_user_id(case.modified_by)
    except KeyError:
        return

    if modified_by:
        result['case']['last_modified_by'] = _get_obj_template_info(modified_by)


def get_message_template_params(case=None):
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
        "owner": ... dict with selected info for the case owner ...
        "last_modified_by": ... dict with selected info for the user who last modified the case ...
    }
    """
    result = {}
    if case:
        _add_case_to_template_params(case, result)
        _add_parent_case_to_template_params(case, result)
        _add_owner_to_template_params(case, result)
        _add_modified_by_to_template_params(case, result)
    return result


def get_custom_content_handler(handler, logged_event):
    content_handler = None
    if handler.custom_content_handler:
        if handler.custom_content_handler in settings.ALLOWED_CUSTOM_CONTENT_HANDLERS:
            try:
                content_handler = to_function(
                    settings.ALLOWED_CUSTOM_CONTENT_HANDLERS[handler.custom_content_handler])
            except Exception:
                logged_event.error(MessagingEvent.ERROR_CANNOT_LOAD_CUSTOM_CONTENT_HANDLER)
        else:
            logged_event.error(MessagingEvent.ERROR_INVALID_CUSTOM_CONTENT_HANDLER)

    return (handler.custom_content_handler is not None, content_handler)


def fire_sms_event(reminder, handler, recipients, verified_numbers, logged_event, workflow=None):
    current_event = reminder.current_event
    case = reminder.case
    template_params = get_message_template_params(case)

    uses_custom_content_handler, content_handler = get_custom_content_handler(handler, logged_event)
    if uses_custom_content_handler and not content_handler:
        return

    domain_obj = Domain.get_by_name(reminder.domain, strict=True)
    for recipient in recipients:
        logged_subevent = logged_event.create_subevent(handler, reminder, recipient)

        try:
            lang = recipient.get_language_code()
        except Exception:
            lang = None

        if content_handler:
            message = content_handler(reminder, handler, recipient)
        else:
            message = current_event.message.get(lang, current_event.message[handler.default_lang])
            try:
                message = Message.render(message, **template_params)
            except Exception:
                logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
                continue

        verified_number, unverified_number = get_recipient_phone_number(
            reminder, recipient, verified_numbers)

        if message:
            metadata = MessageMetadata(
                workflow=workflow or get_workflow(handler),
                reminder_id=reminder._id,
                messaging_subevent_id=logged_subevent.pk,
            )
            if verified_number is not None:
                send_sms_to_verified_number(verified_number,
                    message, metadata, logged_subevent=logged_subevent)
            elif isinstance(recipient, CouchUser) and unverified_number:
                send_sms(reminder.domain, recipient, unverified_number,
                    message, metadata)
            elif (is_commcarecase(recipient) and unverified_number and
                    domain_obj.send_to_duplicated_case_numbers):
                send_sms(reminder.domain, recipient, unverified_number,
                    message, metadata)
            else:
                logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)
                continue

        logged_subevent.completed()


def fire_sms_callback_event(reminder, handler, recipients, verified_numbers, logged_event):
    current_event = reminder.current_event

    for recipient in recipients:
        send_message = False
        if reminder.callback_try_count > 0:
            if reminder.event_initiation_timestamp:
                event = ExpectedCallback.by_domain_recipient_date(
                    reminder.domain,
                    recipient.get_id,
                    reminder.event_initiation_timestamp
                )
                if not event:
                    continue
                if event.status == CALLBACK_RECEIVED:
                    continue
                if Call.inbound_entry_exists(
                    recipient.doc_type,
                    recipient.get_id,
                    reminder.event_initiation_timestamp
                ):
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
            event = ExpectedCallback.objects.create(
                domain=reminder.domain,
                date=reminder.event_initiation_timestamp,
                couch_recipient_doc_type=recipient.doc_type,
                couch_recipient=recipient.get_id,
                status=CALLBACK_PENDING,
            )

        if send_message:
            fire_sms_event(reminder, handler, [recipient], verified_numbers,
                logged_event, workflow=WORKFLOW_CALLBACK)


def fire_sms_survey_event(reminder, handler, recipients, verified_numbers, logged_event):
    if reminder.callback_try_count > 0:
        # Handle timeouts
        if handler.submit_partial_forms and (reminder.callback_try_count == len(reminder.current_event.callback_timeout_intervals)):
            # Submit partial form completions
            for session_id in reminder.xforms_session_ids:
                submit_unfinished_form(session_id, handler.include_case_side_effects)
        else:
            # Resend current question
            for session_id in reminder.xforms_session_ids:
                session = get_session_by_session_id(session_id)
                if session.end_time is None:
                    vn = verified_numbers.get(session.connection_id)
                    if vn is not None:
                        metadata = MessageMetadata(
                            workflow=get_workflow(handler),
                            reminder_id=reminder._id,
                            xforms_session_couch_id=session._id,
                        )
                        resp = current_question(session_id)
                        send_sms_to_verified_number(vn, resp.event.text_prompt, metadata,
                            logged_subevent=session.related_subevent)
    else:
        reminder.xforms_session_ids = []
        domain_obj = Domain.get_by_name(reminder.domain, strict=True)

        # Get the app, module, and form
        try:
            form_unique_id = reminder.current_event.form_unique_id
            form = Form.get_form(form_unique_id)
            app = form.get_app()
            module = form.get_module()
        except Exception:
            logged_event.error(MessagingEvent.ERROR_CANNOT_FIND_FORM)
            return

        # Start a touchforms session for each recipient
        for recipient in recipients:
            logged_subevent = logged_event.create_subevent(handler, reminder, recipient)

            verified_number, unverified_number = get_recipient_phone_number(
                reminder, recipient, verified_numbers)

            no_verified_number = verified_number is None
            cant_use_unverified_number = (unverified_number is None or
                not domain_obj.send_to_duplicated_case_numbers or
                form_requires_input(form))
            if no_verified_number and cant_use_unverified_number:
                logged_subevent.error(MessagingEvent.ERROR_NO_TWO_WAY_PHONE_NUMBER)
                continue

            key = "start-sms-survey-for-contact-%s" % recipient.get_id
            with CriticalSection([key], timeout=60):
                # Get the case to submit the form against, if any
                if (is_commcarecase(recipient) and
                    not handler.force_surveys_to_use_triggered_case):
                    case_id = recipient.case_id
                else:
                    case_id = reminder.case_id

                if form.requires_case() and not case_id:
                    logged_subevent.error(MessagingEvent.ERROR_NO_CASE_GIVEN)
                    continue

                # Close all currently open sessions
                SQLXFormsSession.close_all_open_sms_sessions(reminder.domain, recipient.get_id)

                # Start the new session
                try:
                    session, responses = start_session(reminder.domain, recipient,
                        app, module, form, case_id,
                        case_for_case_submission=handler.force_surveys_to_use_triggered_case)
                except TouchformsError as e:
                    human_readable_message = e.response_data.get('human_readable_message', None)

                    logged_subevent.error(MessagingEvent.ERROR_TOUCHFORMS_ERROR,
                        additional_error_text=human_readable_message)

                    if touchforms_error_is_config_error(e):
                        # Don't reraise the exception because this means there are configuration
                        # issues with the form that need to be fixed
                        continue
                    else:
                        # Reraise the exception so that the framework retries it again later
                        raise
                except Exception as e:
                    logged_subevent.error(MessagingEvent.ERROR_TOUCHFORMS_ERROR)
                    # Reraise the exception so that the framework retries it again later
                    raise
                session.survey_incentive = handler.survey_incentive
                session.workflow = get_workflow(handler)
                session.reminder_id = reminder._id
                session.save()

            reminder.xforms_session_ids.append(session.session_id)
            logged_subevent.xforms_session = session
            logged_subevent.save()

            # Send out first message
            if len(responses) > 0:
                message = format_message_list(responses)
                metadata = MessageMetadata(
                    workflow=get_workflow(handler),
                    reminder_id=reminder._id,
                    xforms_session_couch_id=session._id,
                )
                if verified_number:
                    send_sms_to_verified_number(verified_number, message, metadata,
                        logged_subevent=logged_subevent)
                else:
                    send_sms(reminder.domain, recipient, unverified_number,
                        message, metadata)

            logged_subevent.completed()


def fire_ivr_survey_event(reminder, handler, recipients, verified_numbers, logged_event):
    domain_obj = Domain.get_by_name(reminder.domain, strict=True)
    for recipient in recipients:
        initiate_call = True
        if reminder.callback_try_count > 0 and reminder.event_initiation_timestamp:
            initiate_call = not Call.answered_call_exists(
                recipient.doc_type,
                recipient.get_id,
                reminder.event_initiation_timestamp
            )

        if initiate_call:
            if (is_commcarecase(recipient) and
                not handler.force_surveys_to_use_triggered_case):
                case_id = recipient.case_id
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
                    logged_event.pk,
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
                    logged_event.pk,
                    unverified_number=unverified_number,
                    case_id=case_id,
                    case_for_case_submission=handler.force_surveys_to_use_triggered_case,
                    timestamp=CaseReminderHandler.get_now(),
                )
            else:
                # initiate_outbound_call will create the subevent automatically,
                # so since we're not initiating the call here, we have to create
                # the subevent explicitly in order to log the error.
                logged_subevent = logged_event.create_subevent(handler, reminder, recipient)
                logged_subevent.error(MessagingEvent.ERROR_NO_PHONE_NUMBER)


def fire_email_event(reminder, handler, recipients, verified_numbers, logged_event):
    current_event = reminder.current_event
    case = reminder.case
    template_params = get_message_template_params(case)
    email_usage = EmailUsage.get_or_create_usage_record(reminder.domain)
    is_trial = domain_is_on_trial(reminder.domain)

    uses_custom_content_handler, content_handler = get_custom_content_handler(handler, logged_event)
    if uses_custom_content_handler and not content_handler:
        return

    for recipient in recipients:
        logged_subevent = logged_event.create_subevent(handler, reminder, recipient)

        try:
            lang = recipient.get_language_code()
        except Exception:
            lang = None

        if content_handler:
            subject, message = content_handler(reminder, handler, recipient)
        else:
            subject = current_event.subject.get(lang, current_event.subject[handler.default_lang])
            message = current_event.message.get(lang, current_event.message[handler.default_lang])
            try:
                subject = Message.render(subject, **template_params)
                message = Message.render(message, **template_params)
            except Exception:
                logged_subevent.error(MessagingEvent.ERROR_CANNOT_RENDER_MESSAGE)
                continue

        subject = subject or '(No Subject)'
        if message:
            try:
                email_address = recipient.get_email()
            except:
                email_address = None

            if email_address:
                if is_trial and EmailUsage.get_total_count(reminder.domain) >= TRIAL_MAX_EMAILS:
                    logged_subevent.error(MessagingEvent.ERROR_TRIAL_EMAIL_LIMIT_REACHED)
                    continue
                send_mail_async.delay(subject, message, settings.DEFAULT_FROM_EMAIL, [email_address])
                email_usage.update_count()
            else:
                logged_subevent.error(MessagingEvent.ERROR_NO_EMAIL_ADDRESS)
                continue

        logged_subevent.completed()


# The dictionary which maps an event type to its event handling method
EVENT_HANDLER_MAP = {
    METHOD_SMS: fire_sms_event,
    METHOD_SMS_CALLBACK: fire_sms_callback_event,
    METHOD_SMS_SURVEY: fire_sms_survey_event,
    METHOD_IVR_SURVEY: fire_ivr_survey_event,
    METHOD_EMAIL: fire_email_event,
}
