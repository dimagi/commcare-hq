from celery.task import task
from corehq.apps.sms.api import incoming as incoming_sms

@task
def incoming_sms_async(phone_number, text, backend_api):
    incoming_sms(phone_number, text, backend_api)