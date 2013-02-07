import pytz
from pytz import timezone
from datetime import timedelta, datetime, date, time
import re
from couchdbkit.ext.django.schema import *
from django.conf import settings
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.api import send_sms, send_sms_to_verified_number
from corehq.apps.sms.models import CallLog, EventLog, MISSED_EXPECTED_CALLBACK, CommConnectCase
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.groups.models import Group
import logging
from dimagi.utils.parsing import string_to_datetime, json_format_datetime
from dateutil.parser import parse
from corehq.apps.smsforms.models import XFormsSession
from corehq.apps.smsforms.app import start_session
from corehq.apps.app_manager.models import get_app, Form
from corehq.apps.sms.util import format_message_list
from corehq.apps.reminders.util import get_form_name
from touchforms.formplayer.api import current_question
from corehq.apps.sms.mixin import VerifiedNumber
from couchdbkit.exceptions import ResourceConflict
from corehq.apps.sms.util import create_task, close_task, update_task
from corehq.apps.smsforms.app import submit_unfinished_form
from dimagi.utils.couch import LockableMixIn
from dimagi.utils.couch.database import get_db

METHOD_SMS = "sms"
METHOD_SMS_CALLBACK = "callback"
METHOD_SMS_SURVEY = "survey"
METHOD_IVR_SURVEY = "ivr_survey"
METHOD_EMAIL = "email"
METHOD_TEST = "test"
METHOD_SMS_CALLBACK_TEST = "callback_test"

METHOD_CHOICES = [
    METHOD_SMS,
    METHOD_SMS_CALLBACK,
    METHOD_SMS_SURVEY,
    METHOD_IVR_SURVEY,
    METHOD_EMAIL,
    METHOD_TEST,
    METHOD_SMS_CALLBACK_TEST,
]

REPEAT_SCHEDULE_INDEFINITELY = -1

EVENT_AS_SCHEDULE = "SCHEDULE"
EVENT_AS_OFFSET = "OFFSET"
EVENT_INTERPRETATIONS = [EVENT_AS_SCHEDULE, EVENT_AS_OFFSET]

UI_SIMPLE_FIXED = "SIMPLE_FIXED"
UI_COMPLEX = "COMPLEX"
UI_CHOICES = [UI_SIMPLE_FIXED, UI_COMPLEX]

RECIPIENT_USER = "USER"
RECIPIENT_OWNER = "OWNER"
RECIPIENT_CASE = "CASE"
RECIPIENT_SURVEY_SAMPLE = "SURVEY_SAMPLE"
RECIPIENT_CHOICES = [RECIPIENT_USER, RECIPIENT_OWNER, RECIPIENT_CASE, RECIPIENT_SURVEY_SAMPLE]

FIRE_TIME_DEFAULT = "DEFAULT"
FIRE_TIME_CASE_PROPERTY = "CASE_PROPERTY"
FIRE_TIME_CHOICES = [FIRE_TIME_DEFAULT, FIRE_TIME_CASE_PROPERTY]

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
    message = DictProperty()
    callback_timeout_intervals = ListProperty(IntegerProperty)
    form_unique_id = StringProperty()

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
    active = BooleanProperty(default=True)
    case_type = StringProperty()
    nickname = StringProperty()
    default_lang = StringProperty()
    method = StringProperty(choices=METHOD_CHOICES, default="sms")
    ui_type = StringProperty(choices=UI_CHOICES, default=UI_SIMPLE_FIXED)
    recipient = StringProperty(choices=RECIPIENT_CHOICES, default=RECIPIENT_USER)
    ui_frequency = StringProperty(choices=UI_FREQUENCY_CHOICES, default=UI_FREQUENCY_ADVANCED) # This will be used to simplify the scheduling process in the ui
    sample_id = StringProperty()
    
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
    
    # reminder schedule
    events = SchemaListProperty(CaseReminderEvent)
    schedule_length = IntegerProperty()
    event_interpretation = StringProperty(choices=EVENT_INTERPRETATIONS, default=EVENT_AS_OFFSET)
    max_iteration_count = IntegerProperty()
    
    # stop condition
    until = StringProperty()
    
    @classmethod
    def get_now(cls):
        try:
            # for testing purposes only!
            return getattr(cls, 'now')
        except Exception:
            return datetime.utcnow()

    def get_reminder(self, case):
        domain = self.domain
        handler_id = self._id
        case_id = case._id
        
        return CaseReminder.view('reminders/by_domain_handler_case',
            key=[domain, handler_id, case_id],
            include_docs=True,
        ).one()

    def get_reminders(self):
        domain = self.domain
        handler_id = self._id
        return CaseReminder.view('reminders/by_domain_handler_case',
            startkey=[domain, handler_id],
            endkey=[domain, handler_id, {}],
            include_docs=True,
        ).all()
    
    # For use with event_interpretation = EVENT_AS_SCHEDULE
    def get_current_reminder_event_timestamp(self, reminder, recipient, case):
        event = self.events[reminder.current_event_sequence_num]
        if event.fire_time_type == FIRE_TIME_DEFAULT:
            fire_time = event.fire_time
        elif event.fire_time_type == FIRE_TIME_CASE_PROPERTY:
            fire_time = case.get_case_property(event.fire_time_aux)
            try:
                fire_time = parse(fire_time).time()
            except Exception:
                fire_time = DEFAULT_REMINDER_TIME
        else:
            fire_time = DEFAULT_REMINDER_TIME
        
        day_offset = self.start_offset + (self.schedule_length * (reminder.schedule_iteration_num - 1)) + event.day_num
        timestamp = datetime.combine(reminder.start_date, fire_time) + timedelta(days = day_offset)
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
                recipient = CommCareUser.get_by_user_id(case.user_id)
            elif self.recipient == RECIPIENT_CASE:
                recipient = CommConnectCase.get(case._id)
        local_now = CaseReminderHandler.utc_to_local(recipient, now)
        
        case_id = case._id if case is not None else None
        user_id = case.user_id if case is not None else None
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
    def utc_to_local(cls, contact, timestamp):
        """
        Converts the given naive datetime from UTC to the contact's time zone.
        
        contact     The contact whose time zone to use (must be an instance of CommCareMobileContactMixin).
        timestamp   The naive datetime.
        
        return      The converted timestamp, as a naive datetime.
        """
        try:
            time_zone = timezone(str(contact.get_time_zone()))
            utc_datetime = pytz.utc.localize(timestamp)
            local_datetime = utc_datetime.astimezone(time_zone)
            naive_local_datetime = local_datetime.replace(tzinfo=None)
            return naive_local_datetime
        except Exception:
            return timestamp

    @classmethod
    def timestamp_to_utc(cls, contact, timestamp):
        """
        Converts the given naive datetime from the contact's time zone to UTC.
        
        contact     The contact whose time zone to use (must be an instance of CommCareMobileContactMixin).
        timestamp   The naive datetime.
        
        return      The converted timestamp, as a naive datetime.
        """
        try:
            time_zone = timezone(str(contact.get_time_zone()))
            local_datetime = time_zone.localize(timestamp)
            utc_datetime = local_datetime.astimezone(pytz.utc)
            naive_utc_datetime = utc_datetime.replace(tzinfo=None)
            return naive_utc_datetime
        except Exception:
            return timestamp

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
            if (reminder.method in [METHOD_SMS_CALLBACK, METHOD_SMS_CALLBACK_TEST, METHOD_SMS_SURVEY, METHOD_IVR_SURVEY]) and len(reminder.current_event.callback_timeout_intervals) > 0:
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
    
    def get_active(self, reminder, now, case):
        schedule_not_finished = not (self.max_iteration_count != REPEAT_SCHEDULE_INDEFINITELY and reminder.schedule_iteration_num > self.max_iteration_count)
        if case is not None:
            until_not_reached = (not self.condition_reached(case, self.until, now))
            return until_not_reached and schedule_not_finished
        else:
            return schedule_not_finished
    
    def should_fire(self, reminder, now):
        return now > reminder.next_fire

    def fire(self, reminder):
        """
        Sends the message associated with the given CaseReminder's current event.
        
        reminder    The CaseReminder which to fire.
        
        return      True on success, False on failure
        """
        # Prevent circular import
        from .event_handlers import EVENT_HANDLER_MAP
        
        # Retrieve the list of individual recipients
        recipient = reminder.recipient
        
        if isinstance(recipient, CouchUser) or isinstance(recipient, CommCareCase):
            recipients = [recipient]
        elif isinstance(recipient, Group):
            recipients = recipient.get_users(is_active=True, only_commcare=False)
        elif isinstance(recipient, SurveySample):
            recipients = [CommConnectCase.get(case_id) for case_id in recipient.contacts]
        else:
            return False
        
        # Retrieve the corresponding verified number entries for all individual recipients
        verified_numbers = {}
        for r in recipients:
            try:
                verified_number = r.get_verified_number()
            except Exception:
                verified_number = None
            verified_numbers[r.get_id] = verified_number
        
        # Call the appropriate event handler
        event_handler = EVENT_HANDLER_MAP.get(self.method)
        last_fired = self.get_now() # Store the timestamp right before firing to ensure continuity in the callback lookups
        result = event_handler(reminder, self, recipients, verified_numbers)
        reminder.last_fired = last_fired
        return result

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
        condition = case.get_case_property(case_property)
        
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

    def case_changed(self, case, now=None):
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
        
        try:
            if (case.user_id == case._id) or (case.user_id is None):
                user = None
            else:
                user = CommCareUser.get_by_user_id(case.user_id)
        except Exception:
            user = None
        
        if not self.active or case.closed or case.type != self.case_type or (self.recipient == RECIPIENT_USER and not user):
            if reminder:
                reminder.retire()
        else:
            # Retrieve the value of the start property
            actual_start_value = case.get_case_property(self.start_property)
            if self.start_match_type == MATCH_EXACT:
                start_condition_reached = (actual_start_value == self.start_value) and (self.start_value is not None)
            elif self.start_match_type == MATCH_ANY_VALUE:
                start_condition_reached = actual_start_value is not None
            elif self.start_match_type == MATCH_REGEX:
                try:
                    regex = re.compile(self.start_value)
                    start_condition_reached = regex.match(str(actual_start_value)) is not None
                except Exception:
                    start_condition_reached = False
            else:
                start_condition_reached = False
            start_date = case.get_case_property(self.start_date)
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
            if reminder is None:
                if start_condition_reached:
                    reminder = self.spawn_reminder(case, start)
                    reminder.start_condition_datetime = start_condition_datetime
                    self.set_next_fire(reminder, now) # This will fast-forward to the next event that does not occur in the past
            
            # Check to see if the reminder should still be active
            if reminder is not None:
                active = self.get_active(reminder, reminder.next_fire, case)
                if active and not reminder.active:
                    reminder.active = True
                    self.set_next_fire(reminder, now) # This will fast-forward to the next event that does not occur in the past
                else:
                    reminder.active = active
                
                reminder.save()
    
    def datetime_definition_changed(self):
        """
        This method is used to manage updates to CaseReminderHandler's whose start_condition_type == ON_DATETIME.
        """
        reminder = CaseReminder.view('reminders/by_domain_handler_case',
            startkey=[self.domain, self._id],
            endkey=[self.domain, self._id, {}],
            include_docs=True
        ).one()
        
        now = self.get_now()
        
        if self.recipient == RECIPIENT_SURVEY_SAMPLE:
            recipient = SurveySample.get(self.sample_id)
        else:
            # TODO: Need to support sending directly to users / cases without case criteria being set
            recipient = None
        
        if reminder is not None and (reminder.start_condition_datetime != self.start_datetime or not self.active):
            reminder.retire()
            reminder = None
        
        if reminder is None and self.active:
            reminder = self.spawn_reminder(None, self.start_datetime, recipient)
            reminder.start_condition_datetime = self.start_datetime
            self.set_next_fire(reminder, now) # This will fast-forward to the next event that does not occur in the past
            reminder.save()
    
    def save(self, **params):
        super(CaseReminderHandler, self).save(**params)
        if not self.deleted():
            if self.start_condition_type == CASE_CRITERIA:
                cases = CommCareCase.view('hqcase/types_by_domain',
                    reduce=False,
                    startkey=[self.domain],
                    endkey=[self.domain, {}],
                    include_docs=True,
                ).all()
                for case in cases:
                    self.case_changed(case)
            elif self.start_condition_type == ON_DATETIME:
                self.datetime_definition_changed()
    
    @classmethod
    def get_handlers(cls, domain, case_type=None):
        key = [domain]
        if case_type:
            key.append(case_type)
        return cls.view('reminders/handlers_by_domain_case_type',
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
        )

    @classmethod
    def get_all_reminders(cls, domain=None, due_before=None):
        if due_before:
            now_json = json_format_datetime(due_before)
        else:
            now_json = {}

        # domain=None will actually get them all, so this works smoothly
        return CaseReminder.view('reminders/by_next_fire',
            startkey=[domain],
            endkey=[domain, now_json],
            include_docs=True
        ).all()
    
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
                reminder.release_lock()

    def retire(self):
        reminders = self.get_reminders()
        self.doc_type += "-Deleted"
        for reminder in reminders:
            print "Retiring %s" % reminder._id
            reminder.retire()
        self.save()

    def deleted(self):
        return self.doc_type != 'CaseReminderHandler'

class CaseReminder(Document, LockableMixIn):
    """
    Where the CaseReminderHandler is the rule and schedule for sending out reminders,
    a CaseReminder is an instance of that rule as it is being applied to a specific
    CommCareCase. A CaseReminder only applies to a single CommCareCase/CaseReminderHandler
    interaction and is just a representation of the state of the rule in the lifecycle 
    of the CaseReminderHandler.
    """
    domain = StringProperty()                       # Domain
    case_id = StringProperty()                      # Reference to the CommCareCase
    handler_id = StringProperty()                   # Reference to the CaseReminderHandler
    user_id = StringProperty()                      # Reference to the CommCareUser who will receive the SMS messages
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
            try:
                return CommCareUser.get_by_user_id(self.user_id)
            except Exception:
                self.retire()
                return None
        else:
            return None

    @property
    def recipient(self):
        handler = self.handler
        if handler.recipient == RECIPIENT_USER:
            return self.user
        elif handler.recipient == RECIPIENT_CASE:
            return CommConnectCase.get(self.case_id)
        elif handler.recipient == RECIPIENT_SURVEY_SAMPLE:
            return SurveySample.get(self.sample_id)
        elif handler.recipient == RECIPIENT_OWNER:
            case = self.case
            
            owner_id = case.owner_id
            if owner_id is None:
                owner_id = case.user_id
            owner_doc = get_db().get(owner_id)
            
            if owner_doc["doc_type"] == "CommCareUser":
                return CommCareUser.get_by_user_id(owner_id)
            elif owner_doc["doc_type"] == "Group":
                return Group.get(owner_id)
            else:
                return None
        else:
            return None
    
    @property
    def retired(self):
        return self.doc_type.endswith("-Deleted")
    
    def retire(self):
        self.doc_type += "-Deleted"
        self.save()


class SurveyKeyword(Document):
    domain = StringProperty()
    keyword = StringProperty()
    form_unique_id = StringProperty()
    
    def retire(self):
        self.doc_type += "-Deleted"
        self.save()
    
    @property
    def survey_name(self):
        return get_form_name(self.form_unique_id)
    
    @property
    def get_id(self):
        return self._id
    
    @classmethod
    def get_all(cls, domain):
        return cls.view("reminders/survey_keywords",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ).all()
    
    @classmethod
    def get_keyword(cls, domain, keyword):
        return cls.view("reminders/survey_keywords",
            key = [domain, keyword.upper()],
            include_docs=True
        ).one()

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
    reminder_definitions = DictProperty() # Dictionary of SurveySample._id : CaseReminderHandler._id
    delegation_tasks = DictProperty() # Dictionary of {sample id : {contact id : delegation task id, ...}, ...}
    
    def has_started(self, parent_survey_ref):
        samples = [SurveySample.get(sample["sample_id"]) for sample in parent_survey_ref.samples]
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
        return cls.view('reminders/survey_by_domain',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ).all()
    
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
                    "sample_object" : SurveySample.get(sample_id),
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
                    for case_id in list(set(tasks.keys()).difference(cati_sample_data[sample_id]["sample_object"].contacts)):
                        close_task(self.domain, tasks[case_id], submitting_user_id)
                        del wave.delegation_tasks[sample_id][case_id]
            
            # Update / Create tasks for existing / new contacts
            for sample_id, sample_data in cati_sample_data.items():
                task_activation_datetime = CaseReminderHandler.timestamp_to_utc(sample_data["sample_object"], datetime.combine(wave.date, wave.time))
                task_deactivation_datetime = CaseReminderHandler.timestamp_to_utc(sample_data["sample_object"], datetime.combine(wave.end_date, wave.time))
                if sample_id not in wave.delegation_tasks:
                    wave.delegation_tasks[sample_id] = {}
                    for case_id in sample_data["sample_object"].contacts:
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
                    for case_id in sample_data["sample_object"].contacts:
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
