from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.users.models import WebUser
from corehq.form_processor.utils import is_commcarecase
from corehq.util.soft_assert import soft_assert


RISK_PROFILE_FIELD = 'risk_profile'
REQUIRED_FIXTURE_FIELDS = [RISK_PROFILE_FIELD, 'sequence', 'message']


def notify_dimagi_project_admins(domain, message):
    users = list(WebUser.get_dimagi_emails_by_domain(domain))
    # if there isn't a dimagi email in the project, notify admins
    notify_admins = len(users) == 0
    _assert = soft_assert(users, notify_admins=notify_admins, send_to_ops=False)
    _assert(False, message)


def general_health_message_bank_content(reminder, handler, recipient):
    return _generic_message_bank_content('general_health', reminder, handler, recipient)


def mental_health_message_bank_content(reminder, handler, recipient):
    return _generic_message_bank_content('mental_health', reminder, handler, recipient)


def sexual_health_message_bank_content(reminder, handler, recipient):
    return _generic_message_bank_content('sexual_health', reminder, handler, recipient)


def med_adherence_message_bank_content(reminder, handler, recipient):
    return _generic_message_bank_content('med_adherence', reminder, handler, recipient)


def substance_use_message_bank_content(reminder, handler, recipient):
    return _generic_message_bank_content('substance_use', reminder, handler, recipient)


def _generic_message_bank_content(fixture_name, reminder, handler, recipient):
    return _get_message_bank_content(
        fixture_name,
        reminder.domain,
        reminder.schedule_iteration_num,
        reminder.current_event_sequence_num,
        len(handler.events),
        recipient
    )


def general_health_message_bank_content_new(recipient, schedule_instance):
    return _get_message_bank_content_new_framework('general_health', recipient, schedule_instance)


def mental_health_message_bank_content_new(recipient, schedule_instance):
    return _get_message_bank_content_new_framework('mental_health', recipient, schedule_instance)


def sexual_health_message_bank_content_new(recipient, schedule_instance):
    return _get_message_bank_content_new_framework('sexual_health', recipient, schedule_instance)


def med_adherence_message_bank_content_new(recipient, schedule_instance):
    return _get_message_bank_content_new_framework('med_adherence', recipient, schedule_instance)


def substance_use_message_bank_content_new(recipient, schedule_instance):
    return _get_message_bank_content_new_framework('substance_use', recipient, schedule_instance)


def _get_message_bank_content_new_framework(fixture_name, recipient, schedule_instance):
    result = _get_message_bank_content(
        fixture_name,
        schedule_instance.domain,
        schedule_instance.schedule_iteration_num,
        schedule_instance.current_event_num,
        len(schedule_instance.memoized_schedule.memoized_events),
        recipient
    )

    if result:
        return [result]

    return []


def _get_message_bank_content(fixture_name, domain, schedule_iteration_num, current_event_num, num_events,
        recipient):
    message_bank = FixtureDataType.by_domain_tag(domain, fixture_name).first()

    if not message_bank:
        message = "Lookup Table {} not found in {}".format(fixture_name, domain)
        notify_dimagi_project_admins(domain, message=message)
        return None

    fields = message_bank.fields_without_attributes

    if any(field not in fields for field in REQUIRED_FIXTURE_FIELDS):
        message = "{} in {} must have {}".format(
            fixture_name, domain, ','.join(REQUIRED_FIXTURE_FIELDS)
        )
        notify_dimagi_project_admins(domain, message=message)
        return None

    if not is_commcarecase(recipient):
        recipient_id = getattr(recipient, '_id') if hasattr(recipient, '_id') else 'id_unknown'
        message = "recipient {} must be a case in domain {}".format(recipient_id, domain)
        notify_dimagi_project_admins(domain, message=message)
        return None

    try:
        risk_profile = recipient.dynamic_case_properties()[RISK_PROFILE_FIELD]
    except KeyError:
        message = "case {} does not include risk_profile".format(recipient.case_id)
        notify_dimagi_project_admins(domain, message=message)
        return None

    current_message_seq_num = str(
        ((schedule_iteration_num - 1) * num_events) +
        current_event_num + 1
    )
    custom_messages = FixtureDataItem.by_field_value(
        domain, message_bank, RISK_PROFILE_FIELD, risk_profile
    )
    custom_messages = [m for m in custom_messages if m.fields_without_attributes['sequence'] == current_message_seq_num]

    if len(custom_messages) != 1:
        if not custom_messages:
            message = "No message for case {}, risk {}, seq {} in domain {} in fixture {}"
        else:
            message = "Multiple messages for case {}, risk {}, seq {} in domain {} in fixture {}"
        message = message.format(recipient.case_id, risk_profile, current_message_seq_num, domain, fixture_name)
        notify_dimagi_project_admins(domain, message=message)
        return None

    return custom_messages[0].fields_without_attributes['message']
