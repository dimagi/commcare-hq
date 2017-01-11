from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.form_processor.utils import is_commcarecase
from dimagi.utils.logging import notify_exception


def ucla_message_bank_content(reminder, handler, recipient):
    domain = reminder.domain
    message_bank = filter(
        lambda f: f.tag == 'message_bank',
        FixtureDataType.by_domain(domain)
    )

    if not message_bank:
        message = "Lookup Table message_bank not found in {}".format(domain)
        notify_exception(None, message=message)
        return None

    message_bank = message_bank[0]
    attributes = message_bank.fields_without_attributes

    try:
        assert 'risk_profile' in attributes
        assert 'sequence' in attributes
        assert 'message' in attributes
    except AssertionError:
        message = "message_bank in {} must have risk_profile, sequence, and message".format(domain)
        notify_exception(None, message=message)
        return None

    if not is_commcarecase(recipient):
        message = "recipient must be a case"
        notify_exception(None, message=message)
        return None

    case_props = recipient.dynamic_case_properties()
    try:
        assert 'risk_profile' in case_props
    except AssertionError:
        message = "case does not include risk_profile"
        notify_exception(None, message=message)
        return None

    current_message_seq_num = (
        ((reminder.schedule_iteration_num - 1) * len(handler.events)) +
        reminder.current_event_sequence_num + 1
    )

    custom_messages = FixtureDataItem.by_field_value(
        domain, message_bank, "risk_profile", case_props['risk_profile']
    )

    custom_messages = filter(
        lambda m: int(m.fields_without_attributes['sequence']) == current_message_seq_num,
        custom_messages
    )

    if len(custom_messages) != 1:
        if not custom_messages:
            message = "No message for {} in {}".format(current_message_seq_num, domain)
        else:
            message = "Multiple messages for {} in {}".format(current_message_seq_num, domain)
        notify_exception(None, message=message)
        return None

    return custom_messages[0].fields_without_attributes['message']
