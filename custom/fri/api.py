import random
import re
import pytz
from dateutil.parser import parse
from datetime import datetime, timedelta, date
from casexml.apps.case.models import CommCareCase
from custom.fri.models import (
    PROFILE_A,
    PROFILE_B,
    PROFILE_C,
    PROFILE_D,
    PROFILE_E,
    PROFILE_F,
    PROFILE_G,
    FRIMessageBankMessage,
    FRIRandomizedMessage,
)
from corehq.apps.reports import util as report_utils

def letters_only(text):
    return re.sub(r"[^a-zA-Z]", "", text).upper()

def get_interactive_participants(domain):
    cases = CommCareCase.view("hqcase/types_by_domain", key=[domain, "participant"], include_docs=True, reduce=False).all()
    result = []
    timezone = report_utils.get_timezone(None, domain) # Use project timezone only
    current_date = datetime.now(tz=timezone).date()
    for case in cases:
        study_arm = case.get_case_property("study_arm")
        if isinstance(study_arm, basestring) and study_arm.upper() == "A" and not case.closed:
            start_date = case.get_case_property("start_date")
            if not isinstance(start_date, date):
                start_date = parse(start_date).date()
            end_date = start_date + timedelta(days=55)
            if current_date >= start_date and current_date <= end_date:
                result.append(case)
    return result

def get_message_bank(domain, risk_profile=None, for_comparing=False):
    if risk_profile is not None:
        messages = FRIMessageBankMessage.view("fri/message_bank", key=[domain, risk_profile], include_docs=True).all()
    else:
        messages = FRIMessageBankMessage.view("fri/message_bank", startkey=[domain], endkey=[domain, {}], include_docs=True).all()

    if for_comparing:
        result = []
        for message in messages:
            result.append({
                "message" : message,
                "compare_string" : letters_only(message.message),
            })
        return result
    else:
        return messages

def add_metadata(sms, message_bank_messages):
    """
    sms - an instance of FRISMSLog
    message_bank_messages - the result from calling get_message_bank(for_comparing=True)
    """
    text = letters_only(sms.text)
    for entry in message_bank_messages:
        if entry["compare_string"] in text:
            sms.fri_message_bank_message_id = entry["message"]._id
            sms.fri_id = entry["message"].fri_id
            sms.fri_risk_profile = entry["message"].risk_profile
            break
    sms.fri_message_bank_lookup_completed = True
    try:
        sms.save()
    except Exception:
        # No big deal, we'll just perform the lookup again the next time it's needed, and
        # try to save it again then.
        pass

def randomize_messages(case):
    """
    Create a randomized list of 280 messages for the case, based on its risk profile.
    """
    message_list = []
    risk_profiles = case.get_case_property("risk_profiles").upper()

    # Add messages specific to each risk profile
    if PROFILE_A in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_A)
    if PROFILE_B in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_B)
    if PROFILE_C in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_C)
    if PROFILE_D in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_D)
    if PROFILE_E in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_E)
    if PROFILE_F in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_F)

    # Add generic messages to get to 280
    additional_messages_required = 280 - len(message_list)
    if additional_messages_required > 0:
        generic_messages = get_message_bank(case.domain, risk_profile=PROFILE_G)
        random.shuffle(generic_messages)
        for i in range(additional_messages_required):
            message_list.append(generic_messages[i])

    # Randomize the list, and save
    random.shuffle(message_list)
    order = 0
    for message in message_list:
        randomized_message = FRIRandomizedMessage(
            domain = case.domain,
            case_id = case._id,
            message_bank_message_id = message._id,
            order = order,
        )
        randomized_message.save()
        order += 1

def get_randomized_message(case, order):
    return FRIRandomizedMessage.view("fri/randomized_message", key=[case.domain, case._id, order], include_docs=True).one()

def custom_content_handler(reminder, handler, recipient):
    """
    This method is invoked from the reminder event-handling thread to retrieve
    the next message to send.
    """
    case = reminder.case
    order = ((reminder.schedule_iteration_num - 1) * 35) + reminder.current_event_sequence_num
    randomized_message = get_randomized_message(case, order)
    if randomized_message is None:
        randomize_messages(case)
        randomized_message = get_randomized_message(case, order)
    message = FRIMessageBankMessage.get(randomized_message.message_bank_message_id)
    return message.message

