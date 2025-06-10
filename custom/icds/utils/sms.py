import pytz
from datetime import timedelta

from corehq.apps.sms.api import get_utcnow
from corehq.util.timezones.conversions import ServerTime


def get_next_available_time(domain_object, domain_now):
    if domain_object.restricted_sms_times:
        restricted_sms_time = domain_object.restricted_sms_times[0]
        next_available_time = None
        # triggered before the window began on the day
        if domain_now.time() < restricted_sms_time.start_time:
            next_available_time = domain_now.replace(
                hour=restricted_sms_time.start_time.hour,
                minute=restricted_sms_time.start_time.minute,
                second=0)
            next_available_time = next_available_time.astimezone(pytz.utc).replace(tzinfo=None)
        # triggered after the window finished on the day
        elif domain_now.time() > restricted_sms_time.end_time:
            next_available_time = domain_now + timedelta(days=1)
            next_available_time = next_available_time.replace(
                hour=restricted_sms_time.start_time.hour,
                minute=restricted_sms_time.start_time.minute,
                second=0)
            next_available_time = next_available_time.astimezone(pytz.utc).replace(tzinfo=None)
        return next_available_time


def can_send_sms_now():
    # from 9am to 9pm IST
    utcnow = get_utcnow()
    india_timezone = pytz.timezone('Asia/Kolkata')
    server_now = ServerTime(utcnow).user_time(india_timezone).done()
    return 9 <= server_now.hour < 21
