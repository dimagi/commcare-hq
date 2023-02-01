from testil import eq

from corehq.apps.sms.models import MessagingEvent
from ..standard.message_event_display import get_status_display


def test_get_status_display_escapes_error_message():
    class fake_event:
        status = MessagingEvent.STATUS_ERROR
        error_code = None
        additional_error_text = "<&>"

    result = get_status_display(fake_event)
    eq(result, "Error - View details for more information. &lt;&amp;&gt;")
