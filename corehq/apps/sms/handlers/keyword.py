import logging
from corehq.apps.sms.api import (
    MessageMetadata,
    add_msg_tags,
    send_sms_to_verified_number,
)
from dimagi.utils.logging import notify_exception
from corehq.apps.smsforms.app import _get_responses, start_session
from corehq.apps.sms.models import WORKFLOW_KEYWORD
from corehq.apps.sms.messages import *
from corehq.apps.sms.handlers.form_session import validate_answer
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.reminders.models import (
    SurveyKeyword,
    RECIPIENT_SENDER,
    RECIPIENT_OWNER,
    RECIPIENT_USER_GROUP,
    METHOD_SMS,
    METHOD_SMS_SURVEY,
    METHOD_STRUCTURED_SMS,
    REMINDER_TYPE_KEYWORD_INITIATED,
)
from corehq.apps.reminders.util import create_immediate_reminder
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.groups.models import Group
from touchforms.formplayer.api import current_question
from corehq.apps.app_manager.models import Form
from casexml.apps.case.models import CommCareCase
from couchdbkit.exceptions import MultipleResultsFound

class StructuredSMSException(Exception):
    def __init__(self, *args, **kwargs):
        response_text = kwargs.pop("response_text", "")
        xformsresponse = kwargs.pop("xformsresponse", None)
        self.response_text = response_text
        self.xformsresponse = xformsresponse
        super(StructuredSMSException, self).__init__(*args, **kwargs)

def contact_can_use_keyword(v, keyword):
    has_keyword_restrictions = len(keyword.initiator_doc_type_filter) > 0
    can_initiate = v.owner_doc_type in keyword.initiator_doc_type_filter
    if has_keyword_restrictions and not can_initiate:
        return False
    else:
        return True

def handle_global_keywords(v, text, msg, text_words, open_sessions):
    global_keyword = text_words[0]

    global_keywords = {
        "#START": global_keyword_start,
        "#STOP": global_keyword_stop,
        "#CURRENT": global_keyword_current,
    }

    inbound_metadata = MessageMetadata(
        workflow=WORKFLOW_KEYWORD,
    )
    add_msg_tags(msg, inbound_metadata)

    fcn = global_keywords.get(global_keyword, global_keyword_unknown)
    return fcn(v, text, msg, text_words, open_sessions)

def global_keyword_start(v, text, msg, text_words, open_sessions):
    from corehq.apps.reminders.models import SurveyKeyword

    outbound_metadata = MessageMetadata(
        workflow=WORKFLOW_KEYWORD,
    )

    if len(text_words) > 1:
        keyword = text_words[1]
        sk = SurveyKeyword.get_keyword(v.domain, keyword)
        if sk:
            if not contact_can_use_keyword(v, sk):
                return False
            process_survey_keyword_actions(v, sk, text[6:].strip(), msg)
        else:
            message = get_message(MSG_KEYWORD_NOT_FOUND, v, (keyword,))
            send_sms_to_verified_number(v, message, metadata=outbound_metadata)
    else:
        message = get_message(MSG_START_KEYWORD_USAGE, v, 
            (text_words[0],))
        send_sms_to_verified_number(v, message, metadata=outbound_metadata)
    return True

def global_keyword_stop(v, text, msg, text_words, open_sessions):
    XFormsSession.close_all_open_sms_sessions(v.domain, v.owner_id)
    return True

def global_keyword_current(v, text, msg, text_words, open_sessions):
    if len(open_sessions) == 1:
        session = open_sessions[0]
        outbound_metadata = MessageMetadata(
            workflow=session.workflow,
            reminder_id=session.reminder_id,
            xforms_session_couch_id=session._id,
        )
        
        resp = current_question(session.session_id)
        send_sms_to_verified_number(v, resp.event.text_prompt,
            metadata=outbound_metadata)
    return True

def global_keyword_unknown(v, text, msg, text_words, open_sessions):
    message = get_message(MSG_UNKNOWN_GLOBAL_KEYWORD, v, (text_words[0],))
    send_sms_to_verified_number(v, message)
    return True

def handle_domain_keywords(v, text, msg, text_words, sessions):
    any_session_open = len(sessions) > 0
    for survey_keyword in SurveyKeyword.get_all(v.domain):
        args = split_args(text, survey_keyword)
        keyword = args[0].upper()
        if keyword == survey_keyword.keyword.upper():
            if any_session_open and not survey_keyword.override_open_sessions:
                # We don't want to override any open sessions, so just pass and
                # let the form session handler handle the message
                return False
            elif not contact_can_use_keyword(v, survey_keyword):
                # The contact type is not allowed to invoke this keyword
                return False
            else:
                inbound_metadata = MessageMetadata(
                    workflow=WORKFLOW_KEYWORD,
                )
                add_msg_tags(msg, inbound_metadata)
                process_survey_keyword_actions(v, survey_keyword, text, msg)
                return True
    # No keywords matched, so pass the message onto the next handler
    return False

def sms_keyword_handler(v, text, msg):
    text = text.strip()
    if text == "":
        return False

    sessions = XFormsSession.get_all_open_sms_sessions(v.domain, v.owner_id)
    text_words = text.upper().split()

    if text.startswith("#"):
        return handle_global_keywords(v, text, msg, text_words, sessions)
    else:
        return handle_domain_keywords(v, text, msg, text_words, sessions)

def _handle_structured_sms(domain, args, contact_id, session,
    first_question, verified_number, xpath_answer=None):

    form_complete = False
    current_question = first_question
    internal_error_msg = get_message(MSG_TOUCHFORMS_DOWN, verified_number)

    used_named_args = xpath_answer is not None
    answer_num = 0
    while not form_complete:
        if current_question.is_error:
            error_msg = current_question.text_prompt or internal_error_msg
            raise StructuredSMSException(response_text=error_msg,
                xformsresponse=current_question)

        xpath = current_question.event._dict["binding"]
        if used_named_args and xpath in xpath_answer:
            valid, answer, error_msg = validate_answer(current_question.event,
                xpath_answer[xpath], verified_number)
            if not valid:
                raise StructuredSMSException(response_text=error_msg,
                    xformsresponse=current_question)
        elif not used_named_args and answer_num < len(args):
            answer = args[answer_num].strip()
            valid, answer, error_msg = validate_answer(current_question.event,
                answer, verified_number)
            if not valid:
                raise StructuredSMSException(response_text=error_msg,
                    xformsresponse=current_question)
        else:
            # We're out of arguments, so try to leave each remaining question
            # blank and continue
            answer = ""
            if current_question.event._dict.get("required", False):
                error_msg = get_message(MSG_FIELD_REQUIRED,
                    verified_number)
                raise StructuredSMSException(response_text=error_msg,
                    xformsresponse=current_question)

        responses = _get_responses(domain, contact_id, answer, 
            yield_responses=True, session_id=session.session_id,
            update_timestamp=False)
        current_question = responses[-1]

        form_complete = is_form_complete(current_question)
        answer_num += 1

def parse_structured_sms_named_args(args, action, verified_number=None):
    """
    Returns a dictionary of {xpath: answer}
    """
    xpath_answer = {}
    for answer in args:
        answer = answer.strip()
        answer_upper = answer.upper()
        if action.named_args_separator is not None:
            # A separator is used for naming arguments; for example, the "="
            # in "register name=joe age=25"
            answer_parts = answer.partition(action.named_args_separator)
            if answer_parts[1] != action.named_args_separator:
                error_msg = get_message(MSG_EXPECTED_NAMED_ARGS_SEPARATOR,
                    verified_number, (action.named_args_separator,))
                raise StructuredSMSException(response_text=error_msg)
            else:
                arg_name = answer_parts[0].upper().strip()
                xpath = action.named_args.get(arg_name, None)
                if xpath is not None:
                    if xpath in xpath_answer:
                        error_msg = get_message(MSG_MULTIPLE_ANSWERS_FOUND,
                            verified_number,
                            (arg_name,))
                        raise StructuredSMSException(response_text=error_msg)

                    xpath_answer[xpath] = answer_parts[2].strip()
                else:
                    # Ignore unexpected named arguments
                    pass
        else:
            # No separator is used for naming arguments
            # for example, "update a100 b34 c5"
            matches = 0
            for k, v in action.named_args.items():
                if answer_upper.startswith(k):
                    matches += 1
                    if matches > 1:
                        error_msg = get_message(MSG_MULTIPLE_QUESTIONS_MATCH,
                            verified_number,
                            (answer,))
                        raise StructuredSMSException(response_text=error_msg)

                    if v in xpath_answer:
                        error_msg = get_message(MSG_MULTIPLE_ANSWERS_FOUND,
                            verified_number,
                            (k,))
                        raise StructuredSMSException(response_text=error_msg)

                    xpath_answer[v] = answer[len(k):].strip()

            if matches == 0:
                # Ignore unexpected named arguments
                pass
    return xpath_answer

def split_args(text, survey_keyword):
    text = text.strip()
    if survey_keyword.delimiter is not None:
        args = text.split(survey_keyword.delimiter)
    else:
        args = text.split()
    args = [arg.strip() for arg in args]
    return args

def handle_structured_sms(survey_keyword, survey_keyword_action, contact,
    verified_number, text, send_response=False, msg=None, case=None,
    text_args=None):

    domain = contact.domain
    contact_doc_type = contact.doc_type
    contact_id = contact._id

    if text_args is not None:
        args = text_args
    else:
        args = split_args(text, survey_keyword)
        args = args[1:]
    keyword = survey_keyword.keyword.upper()

    error_occurred = False
    error_msg = None
    session = None

    try:
        # Start the session
        app, module, form = get_form(
            survey_keyword_action.form_unique_id, include_app_module=True)

        if case:
            case_id = case._id
        elif contact_doc_type == "CommCareCase":
            case_id = contact_id
        else:
            case_id = None

        session, responses = start_session(domain, contact, app, module,
            form, case_id=case_id, yield_responses=True)
        session.workflow = WORKFLOW_KEYWORD
        session.save()
        assert len(responses) > 0, "There should be at least one response."

        first_question = responses[-1]
        if not is_form_complete(first_question):
            if survey_keyword_action.use_named_args:
                # Arguments in the sms are named
                xpath_answer = parse_structured_sms_named_args(args,
                    survey_keyword_action, verified_number)
                _handle_structured_sms(domain, args, contact_id, session,
                    first_question, verified_number, xpath_answer)
            else:
                # Arguments in the sms are not named; pass each argument to
                # each question in order
                _handle_structured_sms(domain, args, contact_id, session,
                    first_question, verified_number)

    except StructuredSMSException as sse:
        error_occurred = True
        error_msg = ""
        if sse.xformsresponse and sse.xformsresponse.event:
            xpath_arg = None
            if survey_keyword_action.use_named_args:
                xpath_arg = \
                    {v: k for k, v in survey_keyword_action.named_args.items()}
            field_name = get_question_id(sse.xformsresponse, xpath_arg)
            error_msg = get_message(MSG_FIELD_DESCRIPTOR, verified_number,
                (field_name,))
        error_msg = "%s%s" % (error_msg, sse.response_text)
    except Exception:
        notify_exception(None, message=("Could not process structured sms for"
            "contact %s, domain %s, keyword %s" % (contact_id, domain, keyword)))
        error_occurred = True
        error_msg = get_message(MSG_TOUCHFORMS_ERROR, verified_number)

    if session is not None:
        session = XFormsSession.get(session._id)
        if session.is_open:
            session.end(False)
            session.save()

    metadata = MessageMetadata(
        workflow=WORKFLOW_KEYWORD,
        xforms_session_couch_id=session._id if session else None,
    )

    if msg:
        add_msg_tags(msg, metadata)

    if error_occurred and verified_number is not None and send_response:
        send_sms_to_verified_number(verified_number, error_msg, metadata=metadata)

    return not error_occurred

def get_question_id(xformsresponse, xpath_arg=None):
    binding = xformsresponse.event._dict.get("binding", None)
    question_id = None
    if binding:
        if xpath_arg and (binding in xpath_arg):
            question_id = xpath_arg[binding]
        else:
            question_id = binding.split("/")[-1]
    return question_id

def is_form_complete(current_question):
    # Force a return value of either True or False (instead of None)
    if current_question.event and current_question.event.type == "form-complete":
        return True
    else:
        return False

def get_form(form_unique_id, include_app_module=False):
    form = Form.get_form(form_unique_id)
    if include_app_module:
        app = form.get_app()
        module = form.get_module()
        return (app, module, form)
    else:
        return form

def keyword_uses_form_that_requires_case(survey_keyword):
    for action in survey_keyword.actions:
        if action.action in [METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS]:
            form = get_form(action.form_unique_id)
            if form.requires_case():
                return True
    return False

def get_case_by_external_id(domain, external_id, user):
    cases = CommCareCase.view("hqcase/by_domain_external_id",
        key=[domain, external_id],
        include_docs=True,
        reduce=False,
    ).all()

    def filter_fcn(case):
        return not case.closed and user_can_access_case(user, case)
    cases = filter(filter_fcn, cases)

    if len(cases) == 1:
        return (cases[0], 1)
    else:
        return (None, len(cases))

def user_is_owner(user, case):
    return case.owner_id == user._id

def case_is_shared(user, case):
    groups = user.get_case_sharing_groups()
    group_ids = [group._id for group in groups]
    return case.owner_id in group_ids

def access_through_subcases(user, case):
    return any(
        [user_can_access_case(user, subcase) for subcase in case.get_subcases()]
    )

def user_can_access_case(user, case):
    return (
        user_is_owner(user, case) or
        case_is_shared(user, case) or
        access_through_subcases(user, case)
    )

def send_keyword_response(vn, message_id):
    metadata = MessageMetadata(
        workflow=WORKFLOW_KEYWORD,
    )
    message = get_message(message_id, vn)
    send_sms_to_verified_number(vn, message, metadata=metadata)

def process_survey_keyword_actions(verified_number, survey_keyword, text, msg):
    sender = verified_number.owner
    case = None
    args = split_args(text, survey_keyword)

    # Close any open sessions even if it's just an sms that we're
    # responding with.
    XFormsSession.close_all_open_sms_sessions(verified_number.domain,
        verified_number.owner_id)

    if sender.doc_type == "CommCareCase":
        case = sender
        args = args[1:]
    elif sender.doc_type == "CommCareUser":
        if keyword_uses_form_that_requires_case(survey_keyword):
            if len(args) > 1:
                external_id = args[1]
                case, matches = get_case_by_external_id(verified_number.domain,
                    external_id, sender)
                if matches == 0:
                    send_keyword_response(verified_number, MSG_CASE_NOT_FOUND)
                    return
                elif matches > 1:
                    send_keyword_response(verified_number, MSG_MULTIPLE_CASES_FOUND)
                    return
            else:
                send_keyword_response(verified_number, MSG_MISSING_EXTERNAL_ID)
                return
            args = args[2:]
        else:
            args = args[1:]
    def cmp_fcn(a1, a2):
        a1_ss = (a1.action == METHOD_STRUCTURED_SMS)
        a2_ss = (a2.action == METHOD_STRUCTURED_SMS)
        if a1_ss and a2_ss:
            return 0
        elif a1_ss:
            return -1
        elif a2_ss:
            return 1
        else:
            return 0
    # Process structured sms actions first
    actions = sorted(survey_keyword.actions, cmp=cmp_fcn)
    for survey_keyword_action in actions:
        if survey_keyword_action.recipient == RECIPIENT_SENDER:
            contact = sender
        elif survey_keyword_action.recipient == RECIPIENT_OWNER:
            if sender.doc_type == "CommCareCase":
                contact = get_wrapped_owner(get_owner_id(sender))
            else:
                contact = None
        elif survey_keyword_action.recipient == RECIPIENT_USER_GROUP:
            try:
                contact = Group.get(survey_keyword_action.recipient_id)
                assert contact.doc_type == "Group"
                assert contact.domain == verified_number.domain
            except Exception:
                contact = None
        else:
            contact = None

        if contact is None:
            continue

        if survey_keyword_action.action == METHOD_SMS:
            create_immediate_reminder(contact, METHOD_SMS, 
                reminder_type=REMINDER_TYPE_KEYWORD_INITIATED,
                message=survey_keyword_action.message_content,
                case=case)
        elif survey_keyword_action.action == METHOD_SMS_SURVEY:
            create_immediate_reminder(contact, METHOD_SMS_SURVEY,
                reminder_type=REMINDER_TYPE_KEYWORD_INITIATED,
                form_unique_id=survey_keyword_action.form_unique_id,
                case=case)
        elif survey_keyword_action.action == METHOD_STRUCTURED_SMS:
            res = handle_structured_sms(survey_keyword, survey_keyword_action,
                sender, verified_number, text, send_response=True, msg=msg,
                case=case, text_args=args)
            if not res:
                # If the structured sms processing wasn't successful, don't
                # process any of the other actions
                return

