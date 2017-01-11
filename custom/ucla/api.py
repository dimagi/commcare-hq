from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.form_processor.utils import is_commcarecase
from dimagi.utils.logging import notify_exception


RISK_PROFILE_FIELD = 'risk_profile'
REQUIRED_FIXTURE_FIELDS = [RISK_PROFILE_FIELD, 'sequence', 'message']


def ucla_message_bank_content(reminder, handler, recipient):
    domain = reminder.domain
    message_bank = FixtureDataType.by_domain_tag(domain, 'message_bank').first()

    if not message_bank:
        message = "Lookup Table message_bank not found in {}".format(domain)
        notify_exception(None, message=message)
        return None

    fields = message_bank.fields_without_attributes

    if any(field not in fields for field in REQUIRED_FIXTURE_FIELDS):
        message = "message_bank in {} must have {}".format(
            domain, ','.join(REQUIRED_FIXTURE_FIELDS)
        )
        notify_exception(None, message=message)
        return None

    if not is_commcarecase(recipient):
        recipient_id = getattr(recipient, '_id') if hasattr(recipient, '_id') else 'id_unknown'
        message = "recipient {} must be a case in domain {}".format(recipient_id, domain)
        notify_exception(None, message=message)
        return None

    try:
        risk_profile = recipient.dynamic_case_properties()[RISK_PROFILE_FIELD]
    except KeyError:
        message = "case {} does not include risk_profile".format(recipient.case_id)
        notify_exception(None, message=message)
        return None

    current_message_seq_num = str(
        ((reminder.schedule_iteration_num - 1) * len(handler.events)) +
        reminder.current_event_sequence_num + 1
    )
    custom_messages = FixtureDataItem.by_field_value(
        domain, message_bank, RISK_PROFILE_FIELD, risk_profile
    )
    custom_messages = filter(
        lambda m: m.fields_without_attributes['sequence'] == current_message_seq_num,
        custom_messages
    )

    if len(custom_messages) != 1:
        if not custom_messages:
            message = "No message for risk {}, seq {} in domain {}"
        else:
            message = "Multiple messages for risk {}, seq {} in domain {}"
        message = message.format(risk_profile, current_message_seq_num, domain)
        notify_exception(None, message=message)
        return None

    return custom_messages[0].fields_without_attributes['message']
