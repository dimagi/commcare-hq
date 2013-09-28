import random
from custom.apps.fri.models import (
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

def get_message_bank(domain, risk_profile):
    return FRIMessageBankMessage.view("fri/message_bank", key=[domain, risk_profile], include_docs=True).all()

def randomize_messages(case):
    """
    Create a randomized list of 280 messages for the case, based on its risk profile.
    """
    message_list = []
    risk_profiles = case.get_case_property("risk_profiles").upper()

    # Add messages specific to each risk profile
    if PROFILE_A in risk_profiles:
        message_list += get_message_bank(case.domain, PROFILE_A)
    if PROFILE_B in risk_profiles:
        message_list += get_message_bank(case.domain, PROFILE_B)
    if PROFILE_C in risk_profiles:
        message_list += get_message_bank(case.domain, PROFILE_C)
    if PROFILE_D in risk_profiles:
        message_list += get_message_bank(case.domain, PROFILE_D)
    if PROFILE_E in risk_profiles:
        message_list += get_message_bank(case.domain, PROFILE_E)
    if PROFILE_F in risk_profiles:
        message_list += get_message_bank(case.domain, PROFILE_F)

    # Add generic messages to get to 280
    additional_messages_required = 280 - len(message_list)
    if additional_messages_required > 0:
        generic_messages = get_message_bank(case.domain, PROFILE_G)
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

