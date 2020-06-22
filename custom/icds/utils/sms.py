import pytz
from datetime import timedelta

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
