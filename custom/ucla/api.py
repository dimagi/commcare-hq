from corehq.apps.fixtures.models import FixtureDataType
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

    return "custom message"
