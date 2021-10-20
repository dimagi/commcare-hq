from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend, IncomingRequest
from corehq.apps.sms.api import incoming as incoming_sms
from corehq.apps.sms.util import strip_plus
from corehq.apps.ivr.api import log_call
from celery.task import task
from dimagi.utils.logging import notify_exception
from django.conf import settings
from corehq.apps.sms.models import SMS
from .const import (
    EVENT_INCOMING,
    MESSAGE_TYPE_SMS,
    MESSAGE_TYPE_CALL,
    TELERIVET_FAILED_STATUSES,
    DELIVERED,
)
from django.utils.translation import ugettext_noop

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


def process_message_status(sms: SMS, status: str, **kwargs):
    metadata = {}

    if status == DELIVERED:
        metadata['gateway_delivered'] = True

    if status in TELERIVET_FAILED_STATUSES:
        error = kwargs.get('error_message', ugettext_noop('Error occurred'))
        sms.set_system_error(error)

    if metadata:
        if sms.custom_metadata is not None:
            sms.custom_metadata.update(metadata)
        else:
            sms.custom_metadata = metadata
        sms.save()
