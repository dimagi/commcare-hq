import random
import re
import pytz
from dateutil.parser import parse
from datetime import datetime, timedelta, date, time
from casexml.apps.case.models import CommCareCase
from custom.fri.models import (
    PROFILE_A,
    PROFILE_B,
    PROFILE_C,
    PROFILE_D,
    PROFILE_E,
    PROFILE_F,
    PROFILE_G,
    FRIMessageBankMessage,
    FRIRandomizedMessage,
)
from corehq.apps.reports import util as report_utils
from redis_cache.cache import RedisCache
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.timezones import utils as tz_utils
from corehq.apps.domain.models import Domain
from dimagi.utils.logging import notify_exception

# (time, length in minutes), indexed by day, where Monday=0, Sunday=6
WINDOWS = (
    (time(12, 0), 480),
    (time(12, 0), 480),
    (time(12, 0), 780),
    (time(12, 0), 780),
    (time(12, 0), 840),
    (time(15, 30), 630),
    (time(15, 30), 510),
)

def letters_only(text):
    return re.sub(r"[^a-zA-Z]", "", text).upper()

def get_interactive_participants(domain):
    cases = CommCareCase.view("hqcase/types_by_domain", key=[domain, "participant"], include_docs=True, reduce=False).all()
    result = []
    timezone = report_utils.get_timezone(None, domain) # Use project timezone only
    current_date = datetime.now(tz=timezone).date()
    for case in cases:
        study_arm = case.get_case_property("study_arm")
        if isinstance(study_arm, basestring) and study_arm.upper() == "A" and not case.closed:
            start_date = get_date(case, "start_date")
            if start_date is None:
                continue
            end_date = start_date + timedelta(days=55)
            if current_date >= start_date and current_date <= end_date:
                result.append(case)
    return result

def get_message_bank(domain, risk_profile=None, for_comparing=False):
    if risk_profile is not None:
        messages = FRIMessageBankMessage.view("fri/message_bank", key=[domain, risk_profile], include_docs=True).all()
    else:
        messages = FRIMessageBankMessage.view("fri/message_bank", startkey=[domain], endkey=[domain, {}], include_docs=True).all()

    if for_comparing:
        result = []
        for message in messages:
            result.append({
                "message" : message,
                "compare_string" : letters_only(message.message),
            })
        return result
    else:
        return messages

def add_metadata(sms, message_bank_messages):
    """
    sms - an instance of FRISMSLog
    message_bank_messages - the result from calling get_message_bank(for_comparing=True)
    """
    text = letters_only(sms.text)
    for entry in message_bank_messages:
        if entry["compare_string"] in text:
            sms.fri_message_bank_message_id = entry["message"]._id
            sms.fri_id = entry["message"].fri_id
            sms.fri_risk_profile = entry["message"].risk_profile
            break
    sms.fri_message_bank_lookup_completed = True
    try:
        sms.save()
    except Exception:
        # No big deal, we'll just perform the lookup again the next time it's needed, and
        # try to save it again then.
        pass

def randomize_messages(case):
    """
    Create a randomized list of 280 messages for the case, based on its risk profile.
    """
    message_list = []
    risk_profiles = case.get_case_property("risk_profiles").upper()

    # Add messages specific to each risk profile
    if PROFILE_A in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_A)
    if PROFILE_B in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_B)
    if PROFILE_C in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_C)
    if PROFILE_D in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_D)
    if PROFILE_E in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_E)
    if PROFILE_F in risk_profiles:
        message_list += get_message_bank(case.domain, risk_profile=PROFILE_F)

    # Add generic messages to get to 280
    additional_messages_required = 280 - len(message_list)
    if additional_messages_required > 0:
        generic_messages = get_message_bank(case.domain, risk_profile=PROFILE_G)
        random.shuffle(generic_messages)
        for i in range(additional_messages_required):
            message_list.append(generic_messages[i])

    # Randomize the list, and save
    random.shuffle(message_list)
    order = 0
    for message in message_list:
        randomized_message = FRIRandomizedMessage(
            domain = case.domain,
            case_id = case._id,
            message_bank_message_id = message._id,
            order = order,
        )
        randomized_message.save()
        order += 1

def get_redis_client():
    rcache = cache_core.get_redis_default_cache()
    if not isinstance(rcache, RedisCache):
        raise Exception("Could not get redis client. Is redis down?")
    return rcache.raw_client

def already_randomized(case):
    any_message = FRIRandomizedMessage.view(
        "fri/randomized_message",
        startkey=[case.domain, case._id],
        endkey=[case.domain, case._id, {}],
        include_docs=True
    ).first()
    return any_message is not None

def get_randomized_message(case, order):
    if order >= 0 and order <= 279:
        client = get_redis_client()
        lock = client.lock("fri-randomization-%s" % case._id, timeout=300)

        lock.acquire(blocking=True)
        if not already_randomized(case):
            randomize_messages(case)
        lock.release()

        message = FRIRandomizedMessage.view(
            "fri/randomized_message",
            key=[case.domain, case._id, order],
            include_docs=True
        ).one()
        return message
    else:
        return None

def get_date(case, prop):
    value = case.get_case_property(prop)
    # A datetime is a date, but a date is not a datetime
    if isinstance(value, datetime):
        return datetime.date()
    elif isinstance(value, date):
        return value
    elif isinstance(value, basestring):
        try:
            value = parse(value).date()
        except:
            value = None
        return value
    else:
        return None

def get_message_offset(case):
    previous_sunday = get_date(case, "previous_sunday")
    registration_date = get_date(case, "start_date")
    if previous_sunday is not None and registration_date is not None:
        delta = registration_date - previous_sunday
        return delta.days * 5
    else:
        return None

def get_num_missed_windows(case):
    """
    Get the number of reminder events that were missed on registration day.
    """
    domain_obj = Domain.get_by_name(case.domain, strict=True)
    opened_timestamp = tz_utils.adjust_datetime_to_timezone(
        case.opened_on,
        pytz.utc.zone,
        domain_obj.default_timezone
    )
    day_of_week = opened_timestamp.weekday()
    time_of_day = opened_timestamp.time()

    # In order to use timedelta, we need a datetime
    current_time = datetime.combine(date(2000, 1, 1), time_of_day)
    window_time = datetime.combine(date(2000, 1, 1), WINDOWS[day_of_week][0])

    if current_time < window_time:
        return 0

    window_interval = (WINDOWS[day_of_week][1] - 60) / 5
    for i in range(1, 5):
        window_time += timedelta(minutes=window_interval)
        if current_time < window_time:
            return i

    return 5

def get_message_number(reminder):
    return ((reminder.schedule_iteration_num - 1) * 35) + reminder.current_event_sequence_num

def custom_content_handler(reminder, handler, recipient, catch_up=False):
    """
    This method is invoked from the reminder event-handling thread to retrieve
    the next message to send.
    """
    case = reminder.case
    if catch_up:
        order = reminder.current_event_sequence_num
    else:
        message_offset = get_message_offset(case)
        try:
            assert message_offset is not None
        except:
            notify_exception(None,
                message=("Couldn't calculate the message offset. Check that "
                         "the right case properties are set."))
            return None
        order = get_message_number(reminder) - message_offset

    num_missed_windows = get_num_missed_windows(case)
    if (((not catch_up) and (order < num_missed_windows)) or
        catch_up and (order >= num_missed_windows)):
        return None

    randomized_message = get_randomized_message(case, order)
    if randomized_message:
        message = FRIMessageBankMessage.get(randomized_message.message_bank_message_id)
        return message.message
    else:
        return None

def catchup_custom_content_handler(reminder, handler, recipient):
    """
    Used to send content that was missed to due registering late in the day.
    """
    return custom_content_handler(reminder, handler, recipient, catch_up=True)

