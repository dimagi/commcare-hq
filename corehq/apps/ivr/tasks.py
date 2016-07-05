from celery.task import task
from corehq.apps.ivr import api
from django.conf import settings
from dimagi.utils.logging import notify_exception

DEFAULT_OUTBOUND_RETRY_INTERVAL = 5
DEFAULT_OUTBOUND_RETRIES = 2

OUTBOUND_RETRIES = getattr(settings, "IVR_OUTBOUND_RETRIES",
    DEFAULT_OUTBOUND_RETRIES)

OUTBOUND_RETRY_INTERVAL = getattr(settings, "IVR_OUTBOUND_RETRY_INTERVAL",
    DEFAULT_OUTBOUND_RETRY_INTERVAL)


@task(ignore_result=True)
def initiate_outbound_call(*args, **kwargs):
    retry_num = kwargs.pop("retry_num", 0)
    try:
        if retry_num > 0:
            kwargs.pop("timestamp", None)
        result = api.initiate_outbound_call(*args, **kwargs)
    except Exception:
        notify_exception(None,
            message="Could not initiate outbound call")
        result = False
    if not result:
        if retry_num < OUTBOUND_RETRIES:
            kwargs["retry_num"] = retry_num + 1
            initiate_outbound_call.apply_async(args=args, kwargs=kwargs,
                countdown=(60*OUTBOUND_RETRY_INTERVAL))
