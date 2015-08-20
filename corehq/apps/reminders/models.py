import pytz
from datetime import timedelta, datetime, date, time
import re
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.reminders.dbaccessors import get_surveys_in_domain
from dimagi.ext.couchdbkit import *
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.models import (CommConnectCase, MessagingEvent)
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.users.models import CouchUser
from corehq.apps.groups.models import Group
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.locations.models import SQLLocation
from dimagi.utils.parsing import string_to_datetime, json_format_datetime
from dateutil.parser import parse
from corehq.apps.reminders.util import enqueue_reminder_directly, get_verified_number_for_recipient
from couchdbkit.exceptions import ResourceConflict
from couchdbkit.resource import ResourceNotFound
from corehq.apps.sms.util import create_task, close_task, update_task
from corehq.apps.smsforms.app import submit_unfinished_form
from corehq.util.timezones.conversions import ServerTime, UserTime
from dimagi.utils.couch import LockableMixIn, CriticalSection
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.multithreading import process_fast
from dimagi.utils.logging import notify_exception
from random import randint
from django.conf import settings
from dimagi.utils.couch.database import iter_docs

class IllegalModelStateException(Exception):
    pass

METHOD_SMS = "sms"
METHOD_SMS_CALLBACK = "callback"
METHOD_SMS_SURVEY = "survey"
METHOD_IVR_SURVEY = "ivr_survey"
METHOD_EMAIL = "email"
METHOD_STRUCTURED_SMS = "structured_sms"

METHOD_CHOICES = [
    METHOD_SMS,
    METHOD_SMS_CALLBACK,
    METHOD_SMS_SURVEY,
    METHOD_IVR_SURVEY,
    METHOD_EMAIL,
]

# The Monday - Sunday constants are meant to match the result from
# date.weekday()
DAY_ANY = -1
DAY_MON = 0
DAY_TUE = 1
DAY_WED = 2
DAY_THU = 3
DAY_FRI = 4
DAY_SAT = 5
DAY_SUN = 6

DAY_OF_WEEK_CHOICES = [
    DAY_ANY,
    DAY_MON,
    DAY_TUE,
    DAY_WED,
    DAY_THU,
    DAY_FRI,
    DAY_SAT,
    DAY_SUN,
]

REPEAT_SCHEDULE_INDEFINITELY = -1

EVENT_AS_SCHEDULE = "SCHEDULE"
EVENT_AS_OFFSET = "OFFSET"
EVENT_INTERPRETATIONS = [EVENT_AS_SCHEDULE, EVENT_AS_OFFSET]

UI_SIMPLE_FIXED = "SIMPLE_FIXED"
UI_COMPLEX = "COMPLEX"
UI_CHOICES = [UI_SIMPLE_FIXED, UI_COMPLEX]

RECIPIENT_SENDER = "SENDER"
RECIPIENT_USER = "USER"
RECIPIENT_OWNER = "OWNER"
RECIPIENT_CASE = "CASE"
RECIPIENT_PARENT_CASE = "PARENT_CASE"
RECIPIENT_ALL_SUBCASES = "ALL_SUBCASES"
RECIPIENT_SUBCASE = "SUBCASE"
RECIPIENT_SURVEY_SAMPLE = "SURVEY_SAMPLE"
RECIPIENT_USER_GROUP = "USER_GROUP"
RECIPIENT_LOCATION = "LOCATION"
RECIPIENT_CHOICES = [
    RECIPIENT_USER, RECIPIENT_OWNER, RECIPIENT_CASE, RECIPIENT_SURVEY_SAMPLE,
    RECIPIENT_PARENT_CASE, RECIPIENT_SUBCASE, RECIPIENT_USER_GROUP,
    RECIPIENT_LOCATION,
]

KEYWORD_RECIPIENT_CHOICES = [RECIPIENT_SENDER, RECIPIENT_OWNER, RECIPIENT_USER_GROUP]
KEYWORD_ACTION_CHOICES = [METHOD_SMS, METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS]

FIRE_TIME_DEFAULT = "DEFAULT"
FIRE_TIME_CASE_PROPERTY = "CASE_PROPERTY"
FIRE_TIME_RANDOM = "RANDOM"
FIRE_TIME_CHOICES = [FIRE_TIME_DEFAULT, FIRE_TIME_CASE_PROPERTY, FIRE_TIME_RANDOM]

MATCH_EXACT = "EXACT"
MATCH_REGEX = "REGEX"
MATCH_ANY_VALUE = "ANY_VALUE"
MATCH_TYPE_CHOICES = [MATCH_EXACT, MATCH_REGEX, MATCH_ANY_VALUE]

CASE_CRITERIA = "CASE_CRITERIA"
ON_DATETIME = "ON_DATETIME"
START_CONDITION_TYPES = [CASE_CRITERIA, ON_DATETIME]

SURVEY_METHOD_LIST = ["SMS","CATI"]

UI_FREQUENCY_ADVANCED = "ADVANCED"
UI_FREQUENCY_CHOICES = [UI_FREQUENCY_ADVANCED]

QUESTION_RETRY_CHOICES = [1, 2, 3, 4, 5]

FORM_TYPE_ONE_BY_ONE = "ONE_BY_ONE" # Answer each question one at a time
FORM_TYPE_ALL_AT_ONCE = "ALL_AT_ONCE" # Complete the entire form with just one sms using the delimiter to separate answers
FORM_TYPE_CHOICES = [FORM_TYPE_ONE_BY_ONE, FORM_TYPE_ALL_AT_ONCE]

REMINDER_TYPE_ONE_TIME = "ONE_TIME"
REMINDER_TYPE_KEYWORD_INITIATED = "KEYWORD_INITIATED"
REMINDER_TYPE_DEFAULT = "DEFAULT"
REMINDER_TYPE_SURVEY_MANAGEMENT = "SURVEY_MANAGEMENT"
REMINDER_TYPE_CHOICES = [REMINDER_TYPE_DEFAULT, REMINDER_TYPE_ONE_TIME,
    REMINDER_TYPE_KEYWORD_INITIATED, REMINDER_TYPE_SURVEY_MANAGEMENT]

SEND_NOW = "NOW"
SEND_LATER = "LATER"

# This time is used when the case property used to specify the reminder time isn't a valid time
# TODO: Decide whether to keep this or retire the reminder
DEFAULT_REMINDER_TIME = time(12, 0)

def is_true_value(val):
    return val == 'ok' or val == 'OK'

def looks_like_timestamp(value):
    try:
        regex = re.compile("^\d\d\d\d-\d\d-\d\d.*$")
        return (regex.match(value) is not None)
    except Exception:
        return False

def property_references_parent(case_property):
    return isinstance(case_property, basestring) and case_property.startswith("parent/")

def get_case_property(case, case_property):
    """
    case                the case
    case_property       the name of the case property (can be 'parent/property' to lookup
                        on the parent, or 'property' to lookup on the case)
    """
    if case_property is None or case is None:
        return None
    elif property_references_parent(case_property):
        parent_case = case.parent
        if parent_case is None:
            return None
        else:
            return parent_case.get_case_property(case_property[7:])
    else:
        return case.get_case_property(case_property)

def case_matches_criteria(case, match_type, case_property, value_to_match):
    result = False
    case_property_value = get_case_property(case, case_property)
    if match_type == MATCH_EXACT:
        result = (case_property_value == value_to_match) and (value_to_match is not None)
    elif match_type == MATCH_ANY_VALUE:
        result = case_property_value is not None
    elif match_type == MATCH_REGEX:
        try:
            regex = re.compile(value_to_match)
            result = regex.match(str(case_property_value)) is not None
        except Exception:
            result = False
    
    return result


def get_events_scheduling_info(events):
    """
    Return a list of events as dictionaries, only with information pertinent to scheduling changes.
    """
    result = []
    for e in events:
        result.append({
            "day_num": e.day_num,
            "fire_time": e.fire_time,
            "fire_time_aux": e.fire_time_aux,
            "fire_time_type": e.fire_time_type,
            "time_window_length": e.time_window_length,
            "callback_timeout_intervals": e.callback_timeout_intervals,
            "form_unique_id": e.form_unique_id,
        })
    return result


class MessageVariable(object):
    def __init__(self, variable):
        self.variable = variable

    def __unicode__(self):
        return unicode(self.variable)

    @property
    def days_until(self):
        try: variable = string_to_datetime(self.variable)
        except Exception:
            return "(?)"
        else:
            # add 12 hours and then floor == round to the nearest day
            return (variable - datetime.utcnow() + timedelta(hours=12)).days

    def __getattr__(self, item):
        try:
            return super(MessageVariable, self).__getattribute__(item)
        except Exception:
            pass
        try:
            return MessageVariable(getattr(self.variable, item))
        except Exception:
            pass
        try:
            return MessageVariable(self.variable[item])
        except Exception:
            pass
        return "(?)"

class Message(object):
    def __init__(self, template, **params):
        self.template = template
        self.params = {}
        for key, value in params.items():
            self.params[key] = MessageVariable(value)
    def __unicode__(self):
        return self.template.format(**self.params)

    @classmethod
    def render(cls, template, **params):
        if isinstance(template, str):
            template = unicode(template, encoding='utf-8')
        return unicode(cls(template, **params))

class CaseReminderEvent(DocumentSchema):
    """
    A CaseReminderEvent is the building block for representing reminder schedules in
    a CaseReminderHandler (see CaseReminderHandler.events).

    day_num                     See CaseReminderHandler, depends on event_interpretation.

    fire_time                   See CaseReminderHandler, depends on event_interpretation.
    
    fire_time_aux               Usage depends on fire_time_type.
    
    fire_time_type              FIRE_TIME_DEFAULT: the event will be scheduled at the time specified by fire_time.
                                FIRE_TIME_CASE_PROPERTY: the event will be scheduled at the time specified by the 
                                case property named in fire_time_aux.
                                FIRE_TIME_RANDOM: the event will be scheduled at a random minute on the interval that
                                starts with fire_time and lasts for time_window_length minutes

    time_window_length          Used in FIRE_TIME_RANDOM to define a time interval that starts at fire_time and lasts
                                for this many minutes

    subject                     The subject of the email if the reminder sends an email.
                                This is a dictionary like message is to support translations.

    message                     The text to send along with language to send it, represented 
                                as a dictionary: {"en": "Hello, {user.full_name}, you're having issues."}

    callback_timeout_intervals  For CaseReminderHandlers whose method is "callback", a list of 
                                timeout intervals (in minutes). The message is resent based on 
                                the number of entries in this list until the callback is received, 
                                or the number of timeouts is exhausted.

    form_unique_id              For CaseReminderHandlers whose method is "survey", this the unique id
                                of the form to play as a survey.
    """
    day_num = IntegerProperty()
    fire_time = TimeProperty()
    fire_time_aux = StringProperty()
    fire_time_type = StringProperty(choices=FIRE_TIME_CHOICES, default=FIRE_TIME_DEFAULT)
    time_window_length = IntegerProperty()
    subject = DictProperty()
    message = DictProperty()
    callback_timeout_intervals = ListProperty(IntegerProperty)
    form_unique_id = StringProperty()


def run_rule(case_id, handler, schedule_changed, prev_definition):
    case = CommCareCase.get(case_id)
    try:
        handler.case_changed(case, schedule_changed=schedule_changed,
            prev_definition=prev_definition)
    except ResourceConflict:
        # Sometimes the reminder fires in the middle of reprocessing
        # the scheduling.
        handler.case_changed(case, schedule_changed=schedule_changed,
            prev_definition=prev_definition)
    try:
        client = get_redis_client()
        client.incr("reminder-rule-processing-current-%s" % handler._id)
    except:
        pass


def retire_reminder(reminder_id):
    r = CaseReminder.get(reminder_id)
    r.retire()


def get_case_ids(domain):
    """
    Had to add this because this query kept intermittently raising
    "NoMoreData: Can't parse headers" exceptions.
    """
    max_tries = 5
    for i in range(max_tries):
        try:
            return get_case_ids_in_domain(domain)
        except Exception:
            if i == (max_tries - 1):
                raise


class CaseReminderHandler(Document):
    """
    A CaseReminderHandler defines the rules and schedule which govern how messages 
    should go out. The "start" and "until" attributes will spawn and deactivate a
    CaseReminder for a CommCareCase, respectively, when their conditions are reached. 
    Below both are described in more detail:

    start   This defines when the reminder schedule kicks off.
            Examples:   start="edd"
                            - The reminder schedule kicks off for a CommCareCase on 
                              the date defined by the CommCareCase's "edd" property.
                        start="form_started"
                            - The reminder schedule kicks off for a CommCareCase when 
                              the CommCareCase's "form_started" property equals "ok".

    until   This defines when the reminders should stop being sent. Once this condition 
            is reached, the CaseReminder is deactivated.
            Examples:   until="followup_1_complete"
                            - The reminders will stop being sent for a CommCareCase when 
                              the CommCareCase's "followup_1_complete" property equals "ok".

    Once a CaseReminder is spawned (i.e., when the "start" condition is met for a
    CommCareCase), the intervals at which reminders are sent and the messages sent
    are defined by the "events" attribute on the CaseReminderHandler. 

    One complete cycle through all events is considered to be an "iteration", and the attribute
    that defines the maximum number of iterations for this schedule is "max_iteration_count". 
    Reminder messages will continue to be sent until the events cycle has occurred "max_iteration_count" 
    times, or until the "until" condition is met, whichever comes first. To ignore the "max_iteration_count",
    it can be set to REPEAT_SCHEDULE_INDEFINITELY, in which case only the "until" condition
    stops the reminder messages.

    The events can either be interpreted as offsets from each other and from the original "start" 
    condition, or as fixed schedule times from the original "start" condition:

    Example of "event_interpretation" == EVENT_AS_OFFSET:
        start                   = "form1_completed"
        start_offset            = 1
        events                  = [
            CaseReminderEvent(
                day_num     = 0
               ,fire_time   = time(hour=1)
               ,message     = {"en": "Form not yet completed."}
            )
        ]
        schedule_length         = 0
        event_interpretation    = EVENT_AS_OFFSET
        max_iteration_count     = REPEAT_SCHEDULE_INDEFINITELY
        until                   = "form2_completed"

    This CaseReminderHandler can be used to send an hourly message starting one day (start_offset=1)
    after "form1_completed", and will keep sending the message every hour until "form2_completed". So,
    if "form1_completed" is reached on January 1, 2012, at 9:46am, the reminders will begin being sent
    at January 2, 2012, at 10:46am and every hour subsequently until "form2_completed". Specifically,
    when "event_interpretation" is EVENT_AS_OFFSET:
        day_num         is interpreted to be a number of days after the last fire
        fire_time       is interpreted to be a number of hours, minutes, and seconds after the last fire
        schedule_length is interpreted to be a number of days between the last event and the beginning of a new iteration



    Example of "event_interpretation" == EVENT_AS_SCHEDULE:
        start                   = "regimen_started"
        start_offset            = 1
        events                  = [
            CaseReminderEvent(
                day_num     = 1
               ,fire_time   = time(11,00)
               ,message     = {"en": "Form not yet completed."}
            )
           ,CaseReminderEvent(
                day_num     = 4
               ,fire_time   = time(11,00)
               ,message     = {"en": "Form not yet completed."}
            )
        ]
        schedule_length         = 7
        event_interpretation    = EVENT_AS_SCHEDULE
        max_iteration_count     = 4
        until                   = "ignore_this_attribute"

    This CaseReminderHandler can be used to send reminders at 11:00am on days 2 and 5 of a weekly
    schedule (schedule_length=7), for 4 weeks (max_iteration_count=4). "Day 1" of the weekly schedule
    is considered to be one day (start_offset=1) after "regimen_started". So, if "regimen_started" is
    reached on a Sunday, the days of the week will be Monday=1, Tuesday=2, etc., and the reminders
    will be sent on Tuesday and Friday of each week, for 4 weeks. Specifically, when "event_interpretation" 
    is EVENT_AS_SCHEDULE:
        day_num         is interpreted to be a the number of days since the current event cycle began
        fire_time       is interpreted to be the time of day to fire the reminder
        schedule_length is interpreted to be the length of the event cycle, in days

    Below is a description of the remaining attributes for a CaseReminderHandler:

    domain          The domain to which this CaseReminderHandler belongs. Only CommCareCases belonging to
                    this domain will be checked for the "start" and "until" conditions.

    case_type       Only CommCareCases whose "type" attribute matches this attribute will be checked for 
                    the "start" and "until" conditions.

    nickname        A simple name used to describe this CaseReminderHandler.

    default_lang    Default language to use in case no translation is found for the recipient's language.

    method          Set to "sms" to send simple sms reminders at the proper intervals.
                    Set to "callback" to send sms reminders and to enable the checked of "callback_timeout_intervals" on each event.

    ui_type         The type of UI to use for editing this CaseReminderHandler (see UI_CHOICES)
    """
    domain = StringProperty()
    last_modified = DateTimeProperty()
    active = BooleanProperty(default=True)
    case_type = StringProperty()
    nickname = StringProperty()
    default_lang = StringProperty()
    method = StringProperty(choices=METHOD_CHOICES, default="sms")
    ui_type = StringProperty(choices=UI_CHOICES, default=UI_SIMPLE_FIXED)
    recipient = StringProperty(choices=RECIPIENT_CHOICES, default=RECIPIENT_USER)
    ui_frequency = StringProperty(choices=UI_FREQUENCY_CHOICES, default=UI_FREQUENCY_ADVANCED) # This will be used to simplify the scheduling process in the ui
    sample_id = StringProperty()
    user_group_id = StringProperty()
    user_id = StringProperty()
    case_id = StringProperty()
    reminder_type = StringProperty(choices=REMINDER_TYPE_CHOICES, default=REMINDER_TYPE_DEFAULT)
    locked = BooleanProperty(default=False)

    # Only used when recipient is RECIPIENT_LOCATION
    # All users belonging to these locations will be recipients
    # Should be a list of (Couch model) Location ids
    location_ids = ListProperty()

    # If True, all users belonging to any child locations of the above
    # locations will also be recipients
    include_child_locations = BooleanProperty(default=False)

    # Only used when recipient is RECIPIENT_SUBCASE.
    # All subcases matching the given criteria will be the recipients.
    recipient_case_match_property = StringProperty()
    recipient_case_match_type = StringProperty(choices=MATCH_TYPE_CHOICES)
    recipient_case_match_value = StringProperty()
    
    # Only applies when method is "survey".
    # If this is True, on the last survey timeout, instead of resending the current question, 
    # it will submit the form for the recipient with whatever is completed up to that point.
    submit_partial_forms = BooleanProperty(default=False)
    
    # Only applies when submit_partial_forms is True.
    # If this is True, partial form submissions will be allowed to create / update / close cases.
    # If this is False, partial form submissions will just submit the form without case create / update / close.
    include_case_side_effects = BooleanProperty(default=False)
    
    # Only applies for method = "ivr_survey" right now.
    # This is the maximum number of times that it will retry asking a question with an invalid response before hanging
    # up. This is meant to prevent long running calls.
    max_question_retries = IntegerProperty(choices=QUESTION_RETRY_CHOICES, default=QUESTION_RETRY_CHOICES[-1])
    
    survey_incentive = StringProperty()
    
    # start condition
    start_condition_type = StringProperty(choices=START_CONDITION_TYPES, default=CASE_CRITERIA)
    
    # used when start_condition_type == ON_DATETIME
    start_datetime = DateTimeProperty()
    
    # used when start_condition_type == CASE_CRITERIA
    start_property = StringProperty()
    start_value = StringProperty()
    start_date = StringProperty()
    start_offset = IntegerProperty()
    start_match_type = StringProperty(choices=MATCH_TYPE_CHOICES)
    start_day_of_week = IntegerProperty(choices=DAY_OF_WEEK_CHOICES,
        default=DAY_ANY)
    
    # reminder schedule
    events = SchemaListProperty(CaseReminderEvent)
    schedule_length = IntegerProperty()
    event_interpretation = StringProperty(choices=EVENT_INTERPRETATIONS, default=EVENT_AS_OFFSET)
    max_iteration_count = IntegerProperty()
    
    # stop condition
    until = StringProperty()

    # If present, references an entry in settings.ALLOWED_CUSTOM_CONTENT_HANDLERS, which maps to a function
    # that should be called to retrieve the sms content to send in an sms reminder.
    # The signature of a custom content handler should be function(reminder, handler, recipient)
    custom_content_handler = StringProperty()

    #   If a subcase triggers an SMS survey, but we're sending it to the parent case,
    # we sometimes want the subcase to be the one on which we execute case actions
    # during form submission. This option will allow for that.
    #   Note that this option only makes a difference if a case is filling out the SMS survey,
    # and if a case other than that case triggered the reminder.
    force_surveys_to_use_triggered_case = BooleanProperty(default=False)

    # If this reminder definition is being created as a subevent of a
    # MessagingEvent, this is the id of the MessagingEvent
    messaging_event_id = IntegerProperty()

    # Set this property to filter the recipient list using custom user data.
    # Should be a dictionary where each key is the name of the custom user data
    # field, and each value is a list of allowed values to filter on.
    # For example, if set to:
    #   {'nickname': ['bob', 'jim'],
    #    'phone_type': ['android']}
    # then the recipient list would be filtered to only include users whose phone
    # type is android and whose nickname is either bob or jim.
    # If {}, then no filter is applied to the recipient list.
    user_data_filter = DictProperty()

    @property
    def uses_parent_case_property(self):
        events_use_parent_case_property = False
        for event in self.events:
            if event.fire_time_type == FIRE_TIME_CASE_PROPERTY and property_references_parent(event.fire_time_aux):
                events_use_parent_case_property = True
                break
        return (
            events_use_parent_case_property or
            property_references_parent(self.recipient_case_match_property) or
            property_references_parent(self.start_property) or
            property_references_parent(self.start_date) or
            property_references_parent(self.until)
        )

    @property
    def uses_time_case_property(self):
        for event in self.events:
            if event.fire_time_type == FIRE_TIME_CASE_PROPERTY:
                return True
        return False

    @classmethod
    def get_now(cls):
        try:
            # for testing purposes only!
            return getattr(cls, 'now')
        except Exception:
            return datetime.utcnow()

    def schedule_has_changed(self, old_definition):
        """
        Returns True if the scheduling information in self is different from
        the scheduling information in old_definition.

        old_definition - the CaseReminderHandler to compare to
        """
        return (
            get_events_scheduling_info(old_definition.events) !=
            get_events_scheduling_info(self.events) or
            old_definition.start_offset != self.start_offset or
            old_definition.schedule_length != self.schedule_length or
            old_definition.max_iteration_count != self.max_iteration_count
        )

    def get_reminder(self, case):
        domain = self.domain
        handler_id = self._id
        case_id = case._id
        
        return CaseReminder.view('reminders/by_domain_handler_case',
            key=[domain, handler_id, case_id],
            include_docs=True,
        ).one()

    def get_reminders(self, ids_only=False):
        domain = self.domain
        handler_id = self._id
        include_docs = not ids_only
        result = CaseReminder.view('reminders/by_domain_handler_case',
            startkey=[domain, handler_id],
            endkey=[domain, handler_id, {}],
            include_docs=include_docs,
        ).all()
        if ids_only:
            return [entry["id"] for entry in result]
        else:
            return result

    def get_day_of_week_offset(self, dt, day_of_week):
        offset = 0
        while dt.weekday() != day_of_week:
            offset += 1
            dt = dt + timedelta(days=1)
        return offset

    # For use with event_interpretation = EVENT_AS_SCHEDULE
    def get_current_reminder_event_timestamp(self, reminder, recipient, case):
        event = self.events[reminder.current_event_sequence_num]
        additional_minute_offset = 0
        if event.fire_time_type == FIRE_TIME_DEFAULT:
            fire_time = event.fire_time
        elif event.fire_time_type == FIRE_TIME_CASE_PROPERTY:
            fire_time = get_case_property(case, event.fire_time_aux)
            try:
                fire_time = parse(fire_time).time()
            except Exception:
                fire_time = DEFAULT_REMINDER_TIME
        elif event.fire_time_type == FIRE_TIME_RANDOM:
            additional_minute_offset = randint(0, event.time_window_length - 1) + (event.fire_time.hour * 60) + event.fire_time.minute
            fire_time = time(0, 0)
        else:
            fire_time = DEFAULT_REMINDER_TIME
        
        day_offset = self.start_offset + (self.schedule_length * (reminder.schedule_iteration_num - 1)) + event.day_num
        start_date = reminder.start_date + timedelta(days=day_offset)
        day_of_week_offset = 0
        if self.start_day_of_week != DAY_ANY:
            day_of_week_offset = self.get_day_of_week_offset(start_date,
                self.start_day_of_week)
        timestamp = (datetime.combine(start_date, fire_time) +
            timedelta(days=day_of_week_offset) +
            timedelta(minutes=additional_minute_offset))
        return CaseReminderHandler.timestamp_to_utc(recipient, timestamp)
    
    def spawn_reminder(self, case, now, recipient=None):
        """
        Creates a CaseReminder.
        
        case    The CommCareCase for which to create the CaseReminder.
        now     The date and time to kick off the CaseReminder. This is the date and time from which all
                offsets are calculated.
        
        return  The CaseReminder
        """
        if recipient is None:
            if self.recipient == RECIPIENT_USER:
                recipient = CouchUser.get_by_user_id(case.user_id)
            elif self.recipient == RECIPIENT_CASE:
                recipient = CommConnectCase.get(case._id)
            elif self.recipient == RECIPIENT_PARENT_CASE:
                if case is not None and case.parent is not None:
                    recipient = CommConnectCase.wrap_as_commconnect_case(case.parent)
        local_now = CaseReminderHandler.utc_to_local(recipient, now)
        
        case_id = case._id if case is not None else None
        user_id = recipient._id if self.recipient == RECIPIENT_USER and recipient is not None else None
        sample_id = recipient._id if self.recipient == RECIPIENT_SURVEY_SAMPLE else None
        
        reminder = CaseReminder(
            domain=self.domain,
            case_id=case_id,
            handler_id=self._id,
            user_id=user_id,
            method=self.method,
            active=True,
            start_date=date(now.year, now.month, now.day) if (now.hour == 0 and now.minute == 0 and now.second == 0 and now.microsecond == 0) else date(local_now.year,local_now.month,local_now.day),
            schedule_iteration_num=1,
            current_event_sequence_num=0,
            callback_try_count=0,
            skip_remaining_timeouts=False,
            sample_id=sample_id,
            xforms_session_ids=[],
        )
        # Set the first fire time appropriately
        if self.event_interpretation == EVENT_AS_OFFSET:
            # EVENT_AS_OFFSET
            day_offset = self.start_offset + self.events[0].day_num
            time_offset = self.events[0].fire_time
            reminder.next_fire = now + timedelta(days=day_offset, hours=time_offset.hour, minutes=time_offset.minute, seconds=time_offset.second)
        else:
            # EVENT_AS_SCHEDULE
            reminder.next_fire = self.get_current_reminder_event_timestamp(reminder, recipient, case)
        return reminder

    @classmethod
    def get_contact_timezone_or_utc(cls, contact):
        if not hasattr(contact, 'get_time_zone'):
            return pytz.UTC

        try:
            return pytz.timezone(str(contact.get_time_zone()))
        except:
            return pytz.UTC

    @classmethod
    def utc_to_local(cls, contact, timestamp):
        """
        Converts the given naive datetime from UTC to the contact's time zone.
        
        contact     The contact whose time zone to use (must be an instance of CommCareMobileContactMixin).
        timestamp   The naive datetime.
        
        return      The converted timestamp, as a naive datetime.
        """
        timezone = cls.get_contact_timezone_or_utc(contact)
        return ServerTime(timestamp).user_time(timezone).done().replace(tzinfo=None)

    @classmethod
    def timestamp_to_utc(cls, contact, timestamp):
        """
        Converts the given naive datetime from the contact's time zone to UTC.
        
        contact     The contact whose time zone to use (must be an instance of CommCareMobileContactMixin).
        timestamp   The naive datetime.
        
        return      The converted timestamp, as a naive datetime.
        """
        timezone = cls.get_contact_timezone_or_utc(contact)
        return UserTime(timestamp, timezone).server_time().done().replace(tzinfo=None)

    def move_to_next_event(self, reminder):
        """
        Moves the given CaseReminder to the next event specified by its CaseReminderHandler. If
        the CaseReminder is on the last event in the cycle, it moves to the first event in the cycle.
        
        If the CaseReminderHandler's max_iteration_count is not REPEAT_SCHEDULE_INDEFINITELY and
        the CaseReminder is on the last event in the event cycle, the CaseReminder is also deactivated.
        
        reminder    The CaseReminder to move to the next event.
        
        return      void
        """
        reminder.current_event_sequence_num += 1
        reminder.callback_try_count = 0
        reminder.skip_remaining_timeouts = False
        reminder.xforms_session_ids = []
        reminder.event_initiation_timestamp = None
        if reminder.current_event_sequence_num >= len(self.events):
            reminder.current_event_sequence_num = 0
            reminder.schedule_iteration_num += 1

    def set_next_fire(self, reminder, now):
        """
        Sets reminder.next_fire to the next allowable date after now by continuously moving the 
        given CaseReminder to the next event (using move_to_next_event() above) and setting the 
        CaseReminder's next_fire attribute accordingly until the next_fire > the now parameter. 
        
        This is done to skip reminders that were never sent (such as when reminders are deactivated 
        for a while), instead of sending one reminder every minute until they're all made up for.
        
        reminder    The CaseReminder whose next_fire to set.
        now         The date and time after which reminder.next_fire must be before returning.
        
        return      void
        """
        case = reminder.case
        recipient = reminder.recipient
        iteration = 0
        reminder.error_retry_count = 0
        
        # Reset next_fire to its last scheduled fire time in case there were any error retries
        if reminder.last_scheduled_fire_time is not None:
            reminder.next_fire = reminder.last_scheduled_fire_time
        
        while now >= reminder.next_fire and reminder.active:
            iteration += 1
            # If it is a callback reminder, check the callback_timeout_intervals
            if (self.method in [METHOD_SMS_CALLBACK, METHOD_SMS_SURVEY, METHOD_IVR_SURVEY]
                and len(reminder.current_event.callback_timeout_intervals) > 0):
                if reminder.skip_remaining_timeouts or reminder.callback_try_count >= len(reminder.current_event.callback_timeout_intervals):
                    if self.method == METHOD_SMS_SURVEY and self.submit_partial_forms and iteration > 1:
                        # This is to make sure we submit the unfinished forms even when fast-forwarding to the next event after system downtime
                        for session_id in reminder.xforms_session_ids:
                            submit_unfinished_form(session_id, self.include_case_side_effects)
                else:
                    reminder.next_fire = reminder.next_fire + timedelta(minutes = reminder.current_event.callback_timeout_intervals[reminder.callback_try_count])
                    reminder.callback_try_count += 1
                    continue
            
            # Move to the next event in the cycle
            self.move_to_next_event(reminder)
            
            # Set the next fire time
            if self.event_interpretation == EVENT_AS_OFFSET:
                # EVENT_AS_OFFSET
                next_event = reminder.current_event
                day_offset = next_event.day_num
                if reminder.current_event_sequence_num == 0:
                    day_offset += self.schedule_length
                time_offset = next_event.fire_time
                reminder.next_fire += timedelta(days=day_offset, hours=time_offset.hour, minutes=time_offset.minute, seconds=time_offset.second)
            else:
                # EVENT_AS_SCHEDULE
                reminder.next_fire = self.get_current_reminder_event_timestamp(reminder, recipient, case)
            
            # Set whether or not the reminder should still be active
            reminder.active = self.get_active(reminder, reminder.next_fire, case)
        
        # Preserve the current next fire time since next_fire can be manipulated for error retries
        reminder.last_scheduled_fire_time = reminder.next_fire
    
    def recalculate_schedule(self, reminder, prev_definition=None):
        """
        Recalculates which iteration / event number a schedule-based reminder should be on.
        Only meant to be called on schedule-based reminders.
        """
        if reminder.callback_try_count > 0 and prev_definition is not None and len(prev_definition.events) > reminder.current_event_sequence_num:
            preserve_current_session_ids = True
            old_form_unique_id = prev_definition.events[reminder.current_event_sequence_num].form_unique_id
            old_xforms_session_ids = reminder.xforms_session_ids
        else:
            preserve_current_session_ids = False
        
        case = reminder.case
        
        reminder.last_fired = None
        reminder.error_retry_count = 0
        reminder.event_initiation_timestamp = None
        reminder.active = True
        reminder.schedule_iteration_num = 1
        reminder.current_event_sequence_num = 0
        reminder.callback_try_count = 0
        reminder.skip_remaining_timeouts = False
        reminder.last_scheduled_fire_time = None
        reminder.xforms_session_ids = []
        reminder.next_fire = self.get_current_reminder_event_timestamp(reminder, reminder.recipient, case)
        reminder.active = self.get_active(reminder, reminder.next_fire, case)
        self.set_next_fire(reminder, self.get_now())
        
        if preserve_current_session_ids:
            if reminder.callback_try_count > 0 and self.events[reminder.current_event_sequence_num].form_unique_id == old_form_unique_id and self.method == METHOD_SMS_SURVEY:
                reminder.xforms_session_ids = old_xforms_session_ids
            elif prev_definition is not None and prev_definition.submit_partial_forms:
                for session_id in old_xforms_session_ids:
                    submit_unfinished_form(session_id, prev_definition.include_case_side_effects)
    
    def get_active(self, reminder, now, case):
        schedule_not_finished = not (self.max_iteration_count != REPEAT_SCHEDULE_INDEFINITELY and reminder.schedule_iteration_num > self.max_iteration_count)
        if case is not None:
            until_not_reached = (not self.condition_reached(case, self.until, now))
            return until_not_reached and schedule_not_finished
        else:
            return schedule_not_finished
    
    def should_fire(self, reminder, now):
        return now > reminder.next_fire

    def get_recipient_location_ids(self, locations):
        location_ids = set()
        for location in locations:
            if self.include_child_locations:
                location_ids.update(
                    location.get_descendants(include_self=True).filter(is_archived=False).location_ids()
                )
            else:
                location_ids.add(location.location_id)
        return location_ids

    def apply_user_data_filter(self, recipients):
        if not self.user_data_filter:
            return recipients

        def filter_fcn(recipient):
            if not isinstance(recipient, CouchUser):
                return False

            for key, value in self.user_data_filter.iteritems():
                if recipient.user_data.get(key) not in value:
                    return False

            return True

        return filter(filter_fcn, recipients)

    def fire(self, reminder):
        """
        Sends the content associated with the given CaseReminder's current event.

        reminder - The CaseReminder which to fire.
        return - True to move to the next event, False to not move to the next event.
        """
        from .event_handlers import EVENT_HANDLER_MAP

        if self.deleted():
            reminder.retire()
            return False

        recipient = reminder.recipient
        if self.recipient == RECIPIENT_LOCATION:
            # Use a better name here since recipient is a list of locations
            locations = recipient

            location_ids = self.get_recipient_location_ids(locations)
            recipients = set()
            for location_id in location_ids:
                recipients.update(get_all_users_by_location(self.domain, location_id))
            recipients = list(recipients)
        elif isinstance(recipient, list) and len(recipient) > 0:
            recipients = recipient
        elif isinstance(recipient, CouchUser) or isinstance(recipient, CommCareCase):
            recipients = [recipient]
        elif isinstance(recipient, Group):
            recipients = recipient.get_users(is_active=True, only_commcare=False)
        elif isinstance(recipient, CommCareCaseGroup):
            recipients = [CommConnectCase.get(case_id) for case_id in recipient.cases]
        else:
            recipients = []
            recipient = None

        recipients = self.apply_user_data_filter(recipients)

        if reminder.last_messaging_event_id and reminder.callback_try_count > 0:
            # If we are on one of the timeout intervals, then do not create
            # a new MessagingEvent. Instead, just resuse the one that was
            # created last time.
            logged_event = MessagingEvent.objects.get(pk=reminder.last_messaging_event_id)
        else:
            logged_event = MessagingEvent.create_from_reminder(self, reminder, recipient)
        reminder.last_messaging_event_id = logged_event.pk

        if recipient is None or len(recipients) == 0:
            logged_event.error(MessagingEvent.ERROR_NO_RECIPIENT)
            return True

        # Retrieve the corresponding verified number entries for all individual recipients
        verified_numbers = {}
        for r in recipients:
            verified_numbers[r.get_id] = get_verified_number_for_recipient(r)
        
        # Set the event initiation timestamp if we're not on any timeouts
        if reminder.callback_try_count == 0:
            reminder.event_initiation_timestamp = self.get_now()
        
        # Call the appropriate event handler
        event_handler = EVENT_HANDLER_MAP.get(self.method)
        last_fired = self.get_now() # Store the timestamp right before firing to ensure continuity in the callback lookups
        event_handler(reminder, self, recipients, verified_numbers, logged_event)
        reminder.last_fired = last_fired
        logged_event.completed()
        return True

    @classmethod
    def condition_reached(cls, case, case_property, now):
        """
        Checks to see if the condition specified by case_property on case has been reached.
        If case[case_property] is a timestamp and it is later than now, then the condition is reached.
        If case[case_property] equals "ok", then the condition is reached.
        
        case            The CommCareCase to check.
        case_property   The property on CommCareCase to check.
        now             The timestamp to use when comparing, if case.case_property is a timestamp.
        
        return      True if the condition is reached, False if not.
        """
        condition = get_case_property(case, case_property)
        
        if isinstance(condition, datetime):
            pass
        elif isinstance(condition, date):
            condition = datetime.combine(condition, time(0,0))
        elif looks_like_timestamp(condition):
            try:
                condition = parse(condition)
            except Exception:
                pass
        
        if isinstance(condition, datetime) and getattr(condition, "tzinfo") is not None:
            condition = condition.astimezone(pytz.utc)
            condition = condition.replace(tzinfo=None)
        
        if (isinstance(condition, datetime) and now > condition) or is_true_value(condition):
            return True
        else:
            return False

    def case_changed(self, case, now=None, schedule_changed=False, prev_definition=None):
        key = "rule-update-definition-%s-case-%s" % (self._id, case._id)
        with CriticalSection([key]):
            self._case_changed(case, now, schedule_changed, prev_definition)

    def _case_changed(self, case, now, schedule_changed, prev_definition):
        """
        This method is used to manage updates to CaseReminderHandler's whose start_condition_type == CASE_CRITERIA.
        
        This method is also called every time a CommCareCase is saved and matches this
        CaseReminderHandler's domain and case_type. It's used to check for the
        "start" and "until" conditions in order to spawn or deactivate a CaseReminder
        for the CommCareCase.
        
        case    The case that is being updated.
        now     The current date and time to use; if not specified, datetime.utcnow() is used.
        
        return  void
        """
        now = now or self.get_now()
        reminder = self.get_reminder(case)

        if case and case.user_id and (case.user_id != case._id):
            try:
                user = CouchUser.get_by_user_id(case.user_id)
            except KeyError:
                user = None
        else:
            user = None

        if (case.closed or case.type != self.case_type or
            case.doc_type.endswith("-Deleted") or self.deleted() or
            (self.recipient == RECIPIENT_USER and not user)):
            if reminder:
                reminder.retire()
        else:
            start_condition_reached = case_matches_criteria(case, self.start_match_type, self.start_property, self.start_value)
            start_date = get_case_property(case, self.start_date)
            if (not isinstance(start_date, date)) and not (isinstance(start_date, datetime)):
                try:
                    start_date = parse(start_date)
                except Exception:
                    start_date = None
            
            if isinstance(start_date, datetime):
                start_condition_datetime = start_date
                start = start_date
            elif isinstance(start_date, date):
                start_condition_datetime = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
                start = start_condition_datetime
            else:
                start_condition_datetime = None
                start = now
            
            # Retire the reminder if the start condition is no longer valid
            if reminder is not None:
                if not start_condition_reached:
                    # The start condition is no longer valid, so retire the reminder
                    reminder.retire()
                    reminder = None
                elif reminder.start_condition_datetime != start_condition_datetime:
                    # The start date has changed, so retire the reminder and it will be spawned again in the next block
                    reminder.retire()
                    reminder = None
            
            # Spawn a reminder if need be
            just_spawned = False
            if reminder is None:
                if start_condition_reached:
                    reminder = self.spawn_reminder(case, start)
                    reminder.start_condition_datetime = start_condition_datetime
                    self.set_next_fire(reminder, now) # This will fast-forward to the next event that does not occur in the past
                    just_spawned = True
            
            # Check to see if the reminder should still be active
            if reminder is not None:
                if schedule_changed and self.event_interpretation == EVENT_AS_SCHEDULE and not just_spawned:
                    self.recalculate_schedule(reminder, prev_definition)
                else:
                    active = self.get_active(reminder, reminder.next_fire, case)
                    if active and not reminder.active:
                        reminder.active = True
                        self.set_next_fire(reminder, now) # This will fast-forward to the next event that does not occur in the past
                    else:
                        reminder.active = active

                reminder.active = self.active and reminder.active
                reminder.save()
    
    def datetime_definition_changed(self, send_immediately=False):
        """
        This method is used to manage updates to CaseReminderHandler's whose start_condition_type == ON_DATETIME.
        Set send_immediately to True to send the first event right away, regardless of whether it may occur in the past.
        """
        reminder = CaseReminder.view('reminders/by_domain_handler_case',
            startkey=[self.domain, self._id],
            endkey=[self.domain, self._id, {}],
            include_docs=True
        ).one()
        
        now = self.get_now()
        
        if self.recipient == RECIPIENT_SURVEY_SAMPLE:
            recipient = CommCareCaseGroup.get(self.sample_id)
        elif self.recipient == RECIPIENT_USER_GROUP:
            recipient = Group.get(self.user_group_id)
        elif self.recipient == RECIPIENT_USER:
            recipient = CouchUser.get_by_user_id(self.user_id)
        elif self.recipient == RECIPIENT_CASE:
            recipient = CommCareCase.get(self.case_id)
        elif self.recipient == RECIPIENT_LOCATION:
            recipient = self.locations
        else:
            recipient = None
        
        if reminder is not None and (reminder.start_condition_datetime != self.start_datetime or not self.active):
            reminder.retire()
            reminder = None
        
        if reminder is None and self.active:
            if self.recipient == RECIPIENT_CASE:
                case = recipient
            elif self.case_id is not None:
                case = CommCareCase.get(self.case_id)
            else:
                case = None
            reminder = self.spawn_reminder(case, self.start_datetime, recipient)
            reminder.start_condition_datetime = self.start_datetime
            if settings.REMINDERS_QUEUE_ENABLED:
                reminder.save()
                if send_immediately:
                    enqueue_reminder_directly(reminder)
            else:
                sent = False
                if send_immediately:
                    try:
                        sent = self.fire(reminder)
                    except Exception:
                        # An exception could happen here, for example, if
                        # touchforms is down. So just pass, and let the reminder
                        # be saved below so that the framework will pick it up
                        # and try again.
                        notify_exception(None,
                            message="Error sending immediately for handler %s" %
                            self._id)
                if sent or not send_immediately:
                    self.set_next_fire(reminder, now)
                reminder.save()

    def check_state(self):
        """
        Double-checks the model for any inconsistencies and raises an
        IllegalModelStateException if any exist.
        """
        def check_attr(name, obj=self):
            # don't allow None or empty string, but allow 0
            if getattr(obj, name) in [None, ""]:
                raise IllegalModelStateException("%s is required" % name)

        if self.start_condition_type == CASE_CRITERIA:
            check_attr("case_type")
            check_attr("start_property")
            check_attr("start_match_type")
            if self.start_match_type != MATCH_ANY_VALUE:
                check_attr("start_value")

        if self.start_condition_type == ON_DATETIME:
            check_attr("start_datetime")

        if self.method == METHOD_SMS:
            check_attr("default_lang")

        check_attr("schedule_length")
        check_attr("max_iteration_count")
        check_attr("start_offset")

        if len(self.events) == 0:
            raise IllegalModelStateException("len(events) must be > 0")

        last_day = 0
        for event in self.events:
            check_attr("day_num", obj=event)
            if event.day_num < 0:
                raise IllegalModelStateException("event.day_num must be "
                    "non-negative")

            if event.fire_time_type in [FIRE_TIME_DEFAULT, FIRE_TIME_RANDOM]:
                check_attr("fire_time", obj=event)
            if event.fire_time_type == FIRE_TIME_RANDOM:
                check_attr("time_window_length", obj=event)
            if event.fire_time_type == FIRE_TIME_CASE_PROPERTY:
                check_attr("fire_time_aux", obj=event)

            if self.method == METHOD_SMS and not self.custom_content_handler:
                if not isinstance(event.message, dict):
                    raise IllegalModelStateException("event.message expected "
                        "to be a dictionary")
                if self.default_lang not in event.message:
                    raise IllegalModelStateException("default_lang missing "
                        "from event.message")
            if self.method in [METHOD_SMS_SURVEY, METHOD_IVR_SURVEY]:
                check_attr("form_unique_id", obj=event)

            if not isinstance(event.callback_timeout_intervals, list):
                raise IllegalModelStateException("event."
                    "callback_timeout_intervals expected to be a list")

            last_day = event.day_num

        if self.event_interpretation == EVENT_AS_SCHEDULE:
            if self.schedule_length <= last_day:
                raise IllegalModelStateException("schedule_length must be "
                    "greater than last event's day_num")
        else:
            if self.schedule_length < 0:
                raise IllegalModelStateException("schedule_length must be"
                    "non-negative")

        if self.recipient == RECIPIENT_SUBCASE:
            check_attr("recipient_case_match_property")
            check_attr("recipient_case_match_type")
            if self.recipient_case_match_type != MATCH_ANY_VALUE:
                check_attr("recipient_case_match_value")

        if (self.custom_content_handler and self.custom_content_handler not in
            settings.ALLOWED_CUSTOM_CONTENT_HANDLERS):
            raise IllegalModelStateException("unknown custom_content_handler")

        self.check_min_tick()

    def check_min_tick(self, minutes=60):
        """
        For offset-based schedules that are repeated multiple times
        intraday, makes sure that the events are separated by at least
        the given number of minutes.
        """
        if (self.event_interpretation == EVENT_AS_OFFSET and
            self.max_iteration_count != 1 and self.schedule_length == 0):
            minimum_tick = None
            for e in self.events:
                this_tick = timedelta(days=e.day_num, hours=e.fire_time.hour,
                    minutes=e.fire_time.minute)
                if minimum_tick is None:
                    minimum_tick = this_tick
                elif this_tick < minimum_tick:
                    minimum_tick = this_tick
            if minimum_tick < timedelta(minutes=minutes):
                raise IllegalModelStateException("Minimum tick for a schedule "
                    "repeated multiple times intraday is %s minutes." % minutes)

    @property
    def locations(self):
        """
        Always returns a list of locations even if there is just one.
        Also, ensures that the result returned by this property is
        specifically a list type since filter() returns a QuerySet,
        and other parts of the framework check for the list type.
        """
        return list(SQLLocation.objects.filter(location_id__in=self.location_ids,
            is_archived=False))

    def save(self, **params):
        from corehq.apps.reminders.tasks import process_reminder_rule
        self.check_state()
        schedule_changed = params.pop("schedule_changed", False)
        prev_definition = params.pop("prev_definition", None)
        send_immediately = params.pop("send_immediately", False)
        unlock = params.pop("unlock", False)
        self.last_modified = datetime.utcnow()
        if unlock:
            self.locked = False
        else:
            self.locked = True
        super(CaseReminderHandler, self).save(**params)
        delay = self.start_condition_type == CASE_CRITERIA
        if not unlock:
            if delay:
                process_reminder_rule.delay(self, schedule_changed,
                    prev_definition, send_immediately)
            else:
                process_reminder_rule(self, schedule_changed,
                    prev_definition, send_immediately)

    def process_rule(self, schedule_changed, prev_definition, send_immediately):
        if not self.deleted():
            if self.start_condition_type == CASE_CRITERIA:
                case_ids = get_case_ids(self.domain)
                try:
                    client = get_redis_client()
                    client.set("reminder-rule-processing-current-%s" % self._id,
                        0)
                    client.set("reminder-rule-processing-total-%s" % self._id,
                        len(case_ids))
                except:
                    pass
                process_fast(case_ids, run_rule, item_goal=100, max_threads=5,
                    args=(self, schedule_changed, prev_definition),
                    use_critical_section=False, print_stack_interval=60)
            elif self.start_condition_type == ON_DATETIME:
                self.datetime_definition_changed(send_immediately=send_immediately)
        else:
            reminder_ids = self.get_reminders(ids_only=True)
            process_fast(reminder_ids, retire_reminder, item_goal=100,
                max_threads=5, use_critical_section=False,
                print_stack_interval=60)

    @classmethod
    def get_handlers(cls, domain, reminder_type_filter=None):
        ids = cls.get_handler_ids(domain,
            reminder_type_filter=reminder_type_filter)
        return cls.get_handlers_from_ids(ids)

    @classmethod
    def get_handlers_from_ids(cls, ids):
        return [
            CaseReminderHandler.wrap(doc)
            for doc in iter_docs(cls.get_db(), ids)
        ]

    @classmethod
    def get_upcoming_broadcast_ids(cls, domain):
        utcnow_json = json_format_datetime(datetime.utcnow())
        result = cls.view('reminders/handlers_by_reminder_type',
            startkey=[domain, REMINDER_TYPE_ONE_TIME, utcnow_json],
            endkey=[domain, REMINDER_TYPE_ONE_TIME, {}],
            include_docs=False,
            reduce=False,
        )
        return [row['id'] for row in result]

    @classmethod
    def get_past_broadcast_ids(cls, domain):
        utcnow_json = json_format_datetime(datetime.utcnow())
        result = cls.view('reminders/handlers_by_reminder_type',
            startkey=[domain, REMINDER_TYPE_ONE_TIME, utcnow_json],
            endkey=[domain, REMINDER_TYPE_ONE_TIME],
            include_docs=False,
            reduce=False,
            descending=True,
        )
        return [row['id'] for row in result]

    @classmethod
    def get_handler_ids(cls, domain, reminder_type_filter=None):
        result = cls.view('reminders/handlers_by_reminder_type',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
            reduce=False,
        )

        def filter_fcn(reminder_type):
            if reminder_type_filter is None:
                return True
            else:
                return ((reminder_type or REMINDER_TYPE_DEFAULT) ==
                    reminder_type_filter)
        return [
            row['id'] for row in result
            if filter_fcn(row['key'][1])
        ]

    @classmethod
    def get_referenced_forms(cls, domain):
        handlers = cls.get_handlers(domain)
        referenced_forms = [e.form_unique_id for events in [h.events for h in handlers] for e in events]
        return filter(None, referenced_forms)

    @classmethod
    def get_all_reminders(cls, domain=None, due_before=None, ids_only=False):
        if due_before:
            now_json = json_format_datetime(due_before)
        else:
            now_json = {}

        # domain=None will actually get them all, so this works smoothly
        result = CaseReminder.view('reminders/by_next_fire',
            startkey=[domain],
            endkey=[domain, now_json],
            include_docs=(not ids_only),
        ).all()
        if ids_only:
            return [entry["id"] for entry in result]
        else:
            return result
    
    @classmethod
    def fire_reminders(cls, now=None):
        now = now or cls.get_now()
        for reminder in cls.get_all_reminders(due_before=now):
            if reminder.acquire_lock(now) and now >= reminder.next_fire:
                handler = reminder.handler
                if handler.fire(reminder):
                    handler.set_next_fire(reminder, now)
                    try:
                        reminder.save()
                    except ResourceConflict:
                        # Submitting a form updates the case, which can update the reminder.
                        # Grab the latest version of the reminder and set the next fire if it's still in use.
                        reminder = CaseReminder.get(reminder._id)
                        if not reminder.retired:
                            handler.set_next_fire(reminder, now)
                            reminder.save()
                try:
                    reminder.release_lock()
                except ResourceConflict:
                    # This should go away once we move the locking to Redis
                    reminder = CaseReminder.get(reminder._id)
                    reminder.release_lock()

    def retire(self):
        self.doc_type += "-Deleted"
        self.save()

    def deleted(self):
        return self.doc_type != 'CaseReminderHandler'

class CaseReminder(SafeSaveDocument, LockableMixIn):
    """
    Where the CaseReminderHandler is the rule and schedule for sending out reminders,
    a CaseReminder is an instance of that rule as it is being applied to a specific
    CommCareCase. A CaseReminder only applies to a single CommCareCase/CaseReminderHandler
    interaction and is just a representation of the state of the rule in the lifecycle 
    of the CaseReminderHandler.
    """
    domain = StringProperty()                       # Domain
    last_modified = DateTimeProperty()
    case_id = StringProperty()                      # Reference to the CommCareCase
    handler_id = StringProperty()                   # Reference to the CaseReminderHandler
    user_id = StringProperty()                      # Reference to the CouchUser who will receive the SMS messages
    method = StringProperty(choices=METHOD_CHOICES) # See CaseReminderHandler.method
    next_fire = DateTimeProperty()                  # The date and time that the next message should go out
    last_fired = DateTimeProperty()                 # The date and time that the last message went out
    active = BooleanProperty(default=False)         # True if active, False if deactivated
    start_date = DateProperty()                     # For CaseReminderHandlers with event_interpretation=SCHEDULE, this is the date (in the recipient's time zone) from which all event times are calculated
    schedule_iteration_num = IntegerProperty()      # The current iteration through the cycle of self.handler.events
    current_event_sequence_num = IntegerProperty()  # The current event number (index to self.handler.events)
    callback_try_count = IntegerProperty()          # Keeps track of the number of times a callback has timed out
    skip_remaining_timeouts = BooleanProperty()     # An event handling method can set this to True to skip the remaining timeout intervals for the current event
    start_condition_datetime = DateTimeProperty()   # The date and time matching the case property specified by the CaseReminderHandler.start_condition
    sample_id = StringProperty()
    xforms_session_ids = ListProperty(StringProperty)
    error_retry_count = IntegerProperty(default=0)
    last_scheduled_fire_time = DateTimeProperty()
    event_initiation_timestamp = DateTimeProperty() # The date and time that the event was started (which is the same throughout all timeouts)
    error = BooleanProperty(default=False)
    error_msg = StringProperty()

    # This is the id of the MessagingEvent that was created the
    # last time an event for this reminder fired.
    last_messaging_event_id = IntegerProperty()

    @property
    def handler(self):
        return CaseReminderHandler.get(self.handler_id)

    @property
    def current_event(self):
        return self.handler.events[self.current_event_sequence_num]

    @property
    def case(self):
        if self.case_id is not None:
            return CommCareCase.get(self.case_id)
        else:
            return None

    @property
    def user(self):
        if self.handler.recipient == RECIPIENT_USER:
            return CouchUser.get_by_user_id(self.user_id)
        else:
            return None

    @property
    def recipient(self):
        try:
            return self._recipient_lookup
        except ResourceNotFound:
            return None

    @property
    def _recipient_lookup(self):
        handler = self.handler
        if handler.recipient == RECIPIENT_USER:
            return self.user
        elif handler.recipient == RECIPIENT_CASE:
            return CommConnectCase.get(self.case_id)
        elif handler.recipient == RECIPIENT_SURVEY_SAMPLE:
            return CommCareCaseGroup.get(handler.sample_id)
        elif handler.recipient == RECIPIENT_OWNER:
            return get_wrapped_owner(get_owner_id(self.case))
        elif handler.recipient == RECIPIENT_PARENT_CASE:
            parent_case = None
            case = self.case
            if case is not None:
                parent_case = case.parent
            if parent_case is not None:
                parent_case = CommConnectCase.wrap_as_commconnect_case(parent_case)
            return parent_case
        elif handler.recipient == RECIPIENT_SUBCASE:
            indices = self.case.reverse_indices
            recipients = []
            for index in indices:
                if index.identifier == "parent":
                    subcase = CommConnectCase.get(index.referenced_id)
                    if case_matches_criteria(subcase, handler.recipient_case_match_type, handler.recipient_case_match_property, handler.recipient_case_match_value):
                        recipients.append(subcase)
            return recipients
        elif handler.recipient == RECIPIENT_USER_GROUP:
            return Group.get(handler.user_group_id)
        elif handler.recipient == RECIPIENT_LOCATION:
            return handler.locations
        else:
            return None
    
    @property
    def retired(self):
        return self.doc_type.endswith("-Deleted")

    def save(self, *args, **kwargs):
        self.last_modified = datetime.utcnow()
        super(CaseReminder, self).save(*args, **kwargs)

    def retire(self):
        self.doc_type += "-Deleted"
        self.save()

class SurveyKeywordAction(DocumentSchema):
    recipient = StringProperty(choices=KEYWORD_RECIPIENT_CHOICES)
    recipient_id = StringProperty()
    action = StringProperty(choices=KEYWORD_ACTION_CHOICES)

    # Only used for action == METHOD_SMS
    message_content = StringProperty()

    # Only used for action in [METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS]
    form_unique_id = StringProperty()

    # Only used for action == METHOD_STRUCTURED_SMS
    use_named_args = BooleanProperty()
    named_args = DictProperty() # Dictionary of {argument name in the sms (caps) : form question xpath}
    named_args_separator = StringProperty() # Can be None in which case there is no separator (i.e., a100 b200)

class SurveyKeyword(Document):
    domain = StringProperty()
    keyword = StringProperty()
    description = StringProperty()
    actions = SchemaListProperty(SurveyKeywordAction)
    delimiter = StringProperty() # Only matters if this is a structured SMS: default is None, in which case the delimiter is any consecutive white space
    override_open_sessions = BooleanProperty()
    initiator_doc_type_filter = ListProperty(StringProperty) # List of doc types representing the only types of contacts who should be able to invoke this keyword. Empty list means anyone can invoke.

    # Properties needed for migration and then can be removed
    form_type = StringProperty(choices=FORM_TYPE_CHOICES, default=FORM_TYPE_ONE_BY_ONE)
    form_unique_id = StringProperty()
    use_named_args = BooleanProperty()
    named_args = DictProperty()
    named_args_separator = StringProperty()
    oct13_migration_timestamp = DateTimeProperty()

    def is_structured_sms(self):
        return METHOD_STRUCTURED_SMS in [a.action for a in self.actions]

    def deleted(self):
        return self.doc_type != 'SurveyKeyword'

    def retire(self):
        self.doc_type += "-Deleted"
        self.save()
    
    @property
    def get_id(self):
        return self._id
    
    @classmethod
    def get_all(cls, domain):
        return cls.view("reminders/survey_keywords",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
            reduce=False,
        ).all()
    
    @classmethod
    def get_keyword(cls, domain, keyword):
        return cls.view("reminders/survey_keywords",
            key = [domain, keyword.upper()],
            include_docs=True,
            reduce=False,
        ).one()

    @classmethod
    def get_by_domain(cls, domain, limit=None, skip=None, include_docs=True):
        extra_kwargs = {}
        if limit is not None:
            extra_kwargs['limit'] = limit
        if skip is not None:
            extra_kwargs['skip'] = skip
        return cls.view(
            'reminders/survey_keywords',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=include_docs,
            reduce=False,
            **extra_kwargs
        ).all()


class SurveySample(Document):
    domain = StringProperty()
    name = StringProperty()
    contacts = ListProperty(StringProperty)
    time_zone = StringProperty()
    
    def get_time_zone(self):
        return self.time_zone
    
    @classmethod
    def get_all(cls, domain):
        return cls.view('reminders/sample_by_domain',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ).all()

class SurveyWave(DocumentSchema):
    date = DateProperty()
    time = TimeProperty()
    end_date = DateProperty()
    form_id = StringProperty()
    reminder_definitions = DictProperty() # Dictionary of CommCareCaseGroup._id : CaseReminderHandler._id
    delegation_tasks = DictProperty() # Dictionary of {sample id : {contact id : delegation task id, ...}, ...}
    
    def has_started(self, parent_survey_ref):
        samples = [CommCareCaseGroup.get(sample["sample_id"]) for sample in parent_survey_ref.samples]
        for sample in samples:
            if CaseReminderHandler.timestamp_to_utc(sample, datetime.combine(self.date, self.time)) <= datetime.utcnow():
                return True
        return False


class Survey(Document):
    domain = StringProperty()
    name = StringProperty()
    waves = SchemaListProperty(SurveyWave)
    followups = ListProperty(DictProperty)
    samples = ListProperty(DictProperty)
    send_automatically = BooleanProperty()
    send_followup = BooleanProperty()

    @classmethod
    def get_all(cls, domain):
        return get_surveys_in_domain(domain)

    def has_started(self):
        for wave in self.waves:
            if wave.has_started(self):
                return True
        return False

    def update_delegation_tasks(self, submitting_user_id):
        utcnow = datetime.utcnow()

        # Get info about each CATI sample and the instance of that sample used for this survey
        cati_sample_data = {}
        for sample_json in self.samples:
            if sample_json["method"] == "CATI":
                sample_id = sample_json["sample_id"]
                cati_sample_data[sample_id] = {
                    "sample_object": CommCareCaseGroup.get(sample_id),
                    "incentive" : sample_json["incentive"],
                    "cati_operator" : sample_json["cati_operator"],
                }
        
        for wave in self.waves:
            if wave.has_started(self):
                continue
            
            # Close any tasks for samples that are no longer used, and for contacts that are no longer in the samples
            for sample_id, tasks in wave.delegation_tasks.items():
                if sample_id not in cati_sample_data:
                    for case_id, delegation_case_id in tasks.items():
                        close_task(self.domain, delegation_case_id, submitting_user_id)
                    del wave.delegation_tasks[sample_id]
                else:
                    for case_id in list(set(tasks.keys()).difference(
                            cati_sample_data[sample_id]["sample_object"].cases)):
                        close_task(self.domain, tasks[case_id], submitting_user_id)
                        del wave.delegation_tasks[sample_id][case_id]
            
            # Update / Create tasks for existing / new contacts
            for sample_id, sample_data in cati_sample_data.items():
                task_activation_datetime = CaseReminderHandler.timestamp_to_utc(sample_data["sample_object"], datetime.combine(wave.date, wave.time))
                task_deactivation_datetime = CaseReminderHandler.timestamp_to_utc(sample_data["sample_object"], datetime.combine(wave.end_date, wave.time))
                if sample_id not in wave.delegation_tasks:
                    wave.delegation_tasks[sample_id] = {}
                    for case_id in sample_data["sample_object"].cases:
                        wave.delegation_tasks[sample_id][case_id] = create_task(
                            CommCareCase.get(case_id), 
                            submitting_user_id, 
                            sample_data["cati_operator"], 
                            wave.form_id, 
                            task_activation_datetime,
                            task_deactivation_datetime,
                            sample_data["incentive"]
                        )
                else:
                    for case_id in sample_data["sample_object"].cases:
                        delegation_case_id = wave.delegation_tasks[sample_id].get(case_id, None)
                        if delegation_case_id is None:
                            wave.delegation_tasks[sample_id][case_id] = create_task(
                                CommCareCase.get(case_id), 
                                submitting_user_id, 
                                sample_data["cati_operator"], 
                                wave.form_id, 
                                task_activation_datetime, 
                                task_deactivation_datetime,
                                sample_data["incentive"]
                            )
                        else:
                            delegation_case = CommCareCase.get(delegation_case_id)
                            if (delegation_case.owner_id != sample_data["cati_operator"] or
                            delegation_case.get_case_property("start_date") != task_activation_datetime or
                            delegation_case.get_case_property("end_date") != task_deactivation_datetime or
                            delegation_case.get_case_property("form_id") != wave.form_id):
                                update_task(
                                    self.domain, 
                                    delegation_case_id, 
                                    submitting_user_id, 
                                    sample_data["cati_operator"], 
                                    wave.form_id, 
                                    task_activation_datetime, 
                                    task_deactivation_datetime,
                                    sample_data["incentive"]
                                )


from .signals import *
