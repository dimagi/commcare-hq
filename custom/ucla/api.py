from corehq.apps.fixtures.models import FixtureDataType
from dimagi.utils.logging import notify_exception


def ucla_message_bank_content(reminder, handler, recipient):
    message_bank = filter(
        lambda f: f.tag == 'message_bank',
        FixtureDataType.by_domain(reminder.domain)
    )

    if not message_bank:
        message = "Lookup Table message_bank not found in {}".format(reminder.domain)
        notify_exception(None, message=message)
        return None

    message_bank = message_bank[0]

    return "custom message"
