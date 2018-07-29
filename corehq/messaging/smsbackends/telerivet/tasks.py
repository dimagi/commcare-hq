from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend, IncomingRequest
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.util import strip_plus
from corehq.apps.ivr.api import log_call
from celery.task import task
from dimagi.utils.logging import notify_exception
from django.conf import settings

EVENT_INCOMING = "incoming_message"
MESSAGE_TYPE_SMS = "sms"
MESSAGE_TYPE_MMS = "mms"
MESSAGE_TYPE_USSD = "ussd"
MESSAGE_TYPE_CALL = "call"

CELERY_QUEUE = ("sms_queue" if settings.SMS_QUEUE_ENABLED else
    settings.CELERY_MAIN_QUEUE)


@task(queue=CELERY_QUEUE, ignore_result=True)
def process_incoming_message(*args, **kwargs):
    try:
        from corehq.messaging.smsbackends.telerivet.views import TELERIVET_INBOUND_FIELD_MAP
        fields = {a: kwargs[a] for (a, b) in TELERIVET_INBOUND_FIELD_MAP}
        log = IncomingRequest(**fields)
        log.save()
    except Exception as e:
        notify_exception(None, "Could not save Telerivet log entry")
        pass

    backend = SQLTelerivetBackend.by_webhook_secret(kwargs["secret"])
    if backend is None:
        # Ignore the message if the webhook secret is not recognized
        return

    if kwargs["from_number_e164"]:
        from_number = strip_plus(kwargs["from_number_e164"])
    else:
        from_number = strip_plus(kwargs["from_number"])

    if kwargs["event"] == EVENT_INCOMING:
        if kwargs["message_type"] == MESSAGE_TYPE_SMS:
            domain_scope = backend.domain if not backend.is_global else None
            incoming_sms(from_number, kwargs["content"], SQLTelerivetBackend.get_api_id(),
                domain_scope=domain_scope, backend_id=backend.couch_id)
        elif kwargs["message_type"] == MESSAGE_TYPE_CALL:
            log_call(from_number, "TELERIVET-%s" % kwargs["message_id"], backend=backend)
