from corehq.apps.telerivet.models import TelerivetBackend
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.ivr.api import incoming as incoming_ivr
from celery.task import task

EVENT_INCOMING = "incoming_message"
MESSAGE_TYPE_SMS = "sms"
MESSAGE_TYPE_MMS = "mms"
MESSAGE_TYPE_USSD = "ussd"
MESSAGE_TYPE_CALL = "call"

@task
def process_incoming_message(*args, **kwargs):
    backend = TelerivetBackend.by_webhook_secret(kwargs["secret"])
    if backend is None:
        # Ignore the message if the webhook secret is not recognized
        return

    if kwargs["event"] == EVENT_INCOMING:
        if kwargs["message_type"] == MESSAGE_TYPE_SMS:
            incoming_sms(kwargs["from_number"], kwargs["content"], TelerivetBackend.get_api_id())
        elif kwargs["message_type"] == MESSAGE_TYPE_CALL:
            incoming_ivr(kwargs["from_number"], None,
                "TELERIVET-%s" % kwargs["message_id"], None)

