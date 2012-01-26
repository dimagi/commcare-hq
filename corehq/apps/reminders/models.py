import pytz
from pytz import timezone
from datetime import timedelta, datetime, date
import re
from couchdbkit.ext.django.schema import *
from django.conf import settings
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.api import send_sms
from corehq.apps.users.models import CommCareUser
import logging
from dimagi.utils.parsing import string_to_datetime, json_format_datetime

REPEAT_SCHEDULE_INDEFINITELY = -1

EVENT_AS_SCHEDULE = "SCHEDULE"
EVENT_AS_OFFSET = "OFFSET"
EVENT_INTERPRETATIONS = [EVENT_AS_SCHEDULE, EVENT_AS_OFFSET]

def is_true_value(val):
    return val == 'ok' or val == 'OK'

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
    
METHOD_CHOICES = ["sms", "email", "test", "callback", "callback_test"]

"""
A CaseReminderEvent is the building block for representing reminder schedules in
a CaseReminderHandler (see CaseReminderHandler.events).

day_num                     See CaseReminderHandler, depends on event_interpretation.

fire_time                   See CaseReminderHandler, depends on event_interpretation.

message                     The text to send along with language to send it, represented 
                            as a dictionary: {"en": "Hello, {user.full_name}, you're having issues."}

callback_timeout_intervals  For CaseReminderHandlers whose method is "callback", a list of 
                            timeout intervals (in minutes). The message is resent based on 
                            the number of entries in this list until the callback is received, 
                            or the number of timeouts is exhausted.
"""
class CaseReminderEvent(DocumentSchema):
    day_num = IntegerProperty()
    fire_time = TimeProperty()
    message = DictProperty()
    callback_timeout_intervals = ListProperty(IntegerProperty)

"""
A CaseReminderCallback object logs the callback response for a CaseReminder 
with method "callback".
"""
class CaseReminderCallback(Document):
    phone_number = StringProperty()
    timestamp = DateTimeProperty()
    user_id = StringProperty()
    
    """
    Checks to see if a callback exists for the given user after the given timestamp.
    
    user_id         The user for whom to check the existence of a callback.
    after_timestamp The datetime after which to check for the existence of a callback.
    
    return          True if a callback exists, False if not.
    """
    @classmethod
    def callback_exists(cls, user_id, after_timestamp):
        start_timestamp = json_format_datetime(after_timestamp)
        end_timestamp = json_format_datetime(datetime.utcnow())
        c = CaseReminderCallback.view("reminders/callbacks_by_user_timestamp"
           ,startkey = [user_id, start_timestamp]
           ,endkey = [user_id, end_timestamp]
           ,include_docs = True
        ).one()
        return (c is not None)

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
        Examples:   until="edd"
                        - The reminders will stop being sent for a CommCareCase on 
                          the date defined by the CommCareCase's "edd" property.
                    until="followup_1_complete"
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
at January 2, 2012, at 9:46am and every hour subsequently until "form2_completed". Specifically,
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

lang_property   If given, will be used to select the appropriate translation of a message before it is sent
                out. For example, if this attribute is "lang", the system will check the CaseReminder's 
                user.user_data.lang for the correct language.

default_lang    Default language to use in case the language specified by "lang_property" is not found.

method          Set to "sms" to send simple sms reminders at the proper intervals.
                Set to "callback" to send sms reminders and to enable the checked of "callback_timeout_intervals" on each event.

"""
class CaseReminderHandler(Document):
    domain = StringProperty()
    case_type = StringProperty()
    nickname = StringProperty()
    lang_property = StringProperty()
    default_lang = StringProperty()
    method = StringProperty(choices=METHOD_CHOICES, default="sms")
    
    # Attributes which define the reminder schedule
    start = StringProperty()
    start_offset = IntegerProperty()
    events = SchemaListProperty(CaseReminderEvent)
    schedule_length = IntegerProperty()
    event_interpretation = StringProperty(choices=EVENT_INTERPRETATIONS, default=EVENT_AS_OFFSET)
    max_iteration_count = IntegerProperty()
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

    """
    Creates a CaseReminder.
    
    case    The CommCareCase for which to create the CaseReminder.
    now     The date and time to kick off the CaseReminder. This is the date and time from which all
            offsets are calculated.
    
    return  The CaseReminder
    """
    def spawn_reminder(self, case, now):
        user = CommCareUser.get_by_user_id(case.user_id)
        local_now = CaseReminderHandler.utc_to_local(user, now)
        reminder = CaseReminder(
            domain=self.domain,
            case_id=case._id,
            handler_id=self._id,
            user_id=case.user_id,
            method=self.method,
            active=True,
            lang=self.default_lang,
            start_date=date(local_now.year,local_now.month,local_now.day),
            schedule_iteration_num=1,
            current_event_sequence_num=0,
            callback_try_count=0,
            callback_received=False
        )
        # Set the first fire time appropriately
        if self.event_interpretation == EVENT_AS_OFFSET:
            # EVENT_AS_OFFSET
            day_offset = self.start_offset + self.events[0].day_num
            time_offset = self.events[0].fire_time
            reminder.next_fire = now + timedelta(days=day_offset, hours=time_offset.hour, minutes=time_offset.minute, seconds=time_offset.second)
        else:
            # EVENT_AS_SCHEDULE
            local_tmsp = datetime.combine(reminder.start_date, self.events[0].fire_time) + timedelta(days = (self.start_offset + self.events[0].day_num))
            reminder.next_fire = CaseReminderHandler.timestamp_to_utc(reminder.user, local_tmsp)
        return reminder

    """
    Converts the given naive datetime from UTC to the user's time zone.
    
    user        The user whose time zone to use.
    timestamp   The naive datetime.
    
    return      The converted timestamp, as a naive datetime.
    """
    @classmethod
    def utc_to_local(cls, user, timestamp):
        try:
            time_zone = timezone(user.time_zone)
            utc_datetime = pytz.utc.localize(timestamp)
            local_datetime = utc_datetime.astimezone(time_zone)
            naive_local_datetime = local_datetime.replace(tzinfo=None)
            return naive_local_datetime
        except Exception:
            return timestamp

    """
    Converts the given naive datetime from the user's time zone to UTC.
    
    user        The user whose time zone to use.
    timestamp   The naive datetime.
    
    return      The converted timestamp, as a naive datetime.
    """
    @classmethod
    def timestamp_to_utc(cls, user, timestamp):
        try:
            time_zone = timezone(user.time_zone)
            local_datetime = time_zone.localize(timestamp)
            utc_datetime = local_datetime.astimezone(pytz.utc)
            naive_utc_datetime = utc_datetime.replace(tzinfo=None)
            return naive_utc_datetime
        except Exception:
            return timestamp

    """
    Moves the given CaseReminder to the next event specified by its CaseReminderHandler. If
    the CaseReminder is on the last event in the cycle, it moves to the first event in the cycle.
    
    If the CaseReminderHandler's max_iteration_count is not REPEAT_SCHEDULE_INDEFINITELY and
    the CaseReminder is on the last event in the event cycle, the CaseReminder is also deactivated.
    
    reminder    The CaseReminder to move to the next event.
    
    return      void
    """
    def move_to_next_event(self, reminder):
        reminder.current_event_sequence_num += 1
        reminder.callback_try_count = 0
        reminder.callback_received = False
        if reminder.current_event_sequence_num >= len(self.events):
            reminder.current_event_sequence_num = 0
            reminder.schedule_iteration_num += 1
            if (self.max_iteration_count != REPEAT_SCHEDULE_INDEFINITELY) and (reminder.schedule_iteration_num > self.max_iteration_count):
                reminder.active = False

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
    def set_next_fire(self, reminder, now):
        while now >= reminder.next_fire and reminder.active:
            # If it is a callback reminder, check the callback_timeout_intervals
            if (reminder.method == "callback" or reminder.method == "callback_test") and len(reminder.current_event.callback_timeout_intervals) > 0:
                if reminder.callback_received or reminder.callback_try_count >= len(reminder.current_event.callback_timeout_intervals):
                    pass
                else:
                    reminder.next_fire = reminder.next_fire + timedelta(minutes = reminder.current_event.callback_timeout_intervals[reminder.callback_try_count])
                    reminder.callback_try_count += 1
                    continue
            # Move to the next event in the cycle and set the next fire if it is still active
            self.move_to_next_event(reminder)
            if reminder.active:
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
                    next_event = reminder.current_event
                    day_offset = self.start_offset + (self.schedule_length * (reminder.schedule_iteration_num - 1)) + next_event.day_num
                    reminder_datetime = datetime.combine(reminder.start_date, next_event.fire_time) + timedelta(days = day_offset)
                    reminder.next_fire = CaseReminderHandler.timestamp_to_utc(reminder.user, reminder_datetime)

    def should_fire(self, reminder, now):
        return now > reminder.next_fire

    """
    Sends the message associated with the given CaseReminder's current event.
    
    reminder    The CaseReminder which to fire.
    
    return      True on success, False on failure
    """
    def fire(self, reminder):
        # If it is a callback reminder and the callback has been received, skip sending the next timeout message
        if (reminder.method == "callback" or reminder.method == "callback_test") and len(reminder.current_event.callback_timeout_intervals) > 0:
            if CaseReminderCallback.callback_exists(reminder.user_id, reminder.last_fired):
                reminder.callback_received = True
                return True
        reminder.last_fired = self.get_now()
        message = reminder.current_event.message.get(reminder.lang, reminder.current_event.message[self.default_lang])
        message = Message.render(message, case=reminder.case.case_properties())
        if reminder.method == "sms" or reminder.method == "callback":
            try:
                phone_number = reminder.user.phone_number
            except Exception:
                phone_number = ''

            return send_sms(reminder.domain, reminder.user_id, phone_number, message)
        elif reminder.method == "test" or reminder.method == "callback_test":
            print(message)
            return True
        

    """
    Checks to see if the condition specified by case_property on case has been reached.
    If case[case_property] is a timestamp and it is later than now, then the condition is reached.
    If case[case_property] equals "ok", then the condition is reached.
    
    case            The CommCareCase to check.
    case_property   The property on CommCareCase to check.
    now             The timestamp to use when comparing, if case[case_property] is a timestamp.
    
    return      True if the condition is reached, False if not.
    """
    @classmethod
    def condition_reached(cls, case, case_property, now):
        condition = case.get_case_property(case_property)
        try: condition = string_to_datetime(condition)
        except Exception:
            pass

        if (isinstance(condition, datetime) and condition > now) or is_true_value(condition):
            return True
        else:
            return False

    """
    This method is called every time a CommCareCase is saved and matches this
    CaseReminderHandler's domain and case_type. It's used to check for the
    "start" and "until" conditions in order to spawn or deactivate a CaseReminder
    for the CommCareCase.
    
    case    The case that is being updated.
    now     The current date and time to use; if not specified, datetime.utcnow() is used.
    
    return  void
    """
    def case_changed(self, case, now=None):
        now = now or self.get_now()
        reminder = self.get_reminder(case)

        if case.closed or not CommCareUser.get_by_user_id(case.user_id):
            if reminder:
                reminder.retire()
        else:
            if not reminder:
                start = case.get_case_property(self.start)
                try: start = string_to_datetime(start)
                except Exception:
                    pass
                if isinstance(start, date) or isinstance(start, datetime):
                    if isinstance(start, date):
                        start = datetime(start.year, start.month, start.day, now.hour, now.minute, now.second, now.microsecond)
                    try:
                        reminder = self.spawn_reminder(case, start)
                    except Exception:
                        if settings.DEBUG:
                            raise
                        logging.error(
                            "Case ({case._id}) submitted against "
                            "CaseReminderHandler {self.nickname} ({self._id}) "
                            "but failed to resolve case.{self.start} to a date"
                        )
                else:
                    if self.condition_reached(case, self.start, now):
                        reminder = self.spawn_reminder(case, now)
            else:
                active = (not self.condition_reached(case, self.until, now)) and not (reminder.handler.max_iteration_count != REPEAT_SCHEDULE_INDEFINITELY and reminder.schedule_iteration_num > reminder.handler.max_iteration_count)
                if active and not reminder.active:
                    # if a reminder is reactivated, sending starts over from right now
                    reminder.next_fire = now
                reminder.active = active
            if reminder:
                try:
                    reminder.lang = reminder.user.user_data.get(self.lang_property) or self.default_lang
                except Exception:
                    reminder.lang = self.default_lang
                reminder.save()

    def save(self, **params):
        super(CaseReminderHandler, self).save(**params)
        if not self.deleted():
            cases = CommCareCase.view('hqcase/open_cases',
                reduce=False,
                startkey=[self.domain],
                endkey=[self.domain, {}],
                include_docs=True,
            )
            for case in cases:
                self.case_changed(case)
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
            handler = reminder.handler
            if handler.fire(reminder):
                handler.set_next_fire(reminder, now)
                reminder.save()

    def retire(self):
        reminders = self.get_reminders()
        self.doc_type += "-Deleted"
        for reminder in reminders:
            print "Retiring %s" % reminder._id
            reminder.retire()
        self.save()

    def deleted(self):
        return self.doc_type != 'CaseReminderHandler'

"""
Where the CaseReminderHandler is the rule and schedule for sending out reminders,
a CaseReminder is an instance of that rule as it is being applied to a specific
CommCareCase. A CaseReminder only applies to a single CommCareCase/CaseReminderHandler
interaction and is just a representation of the state of the rule in the lifecycle 
of the CaseReminderHandler.
"""
class CaseReminder(Document):
    domain = StringProperty()                       # Domain
    case_id = StringProperty()                      # Reference to the CommCareCase
    handler_id = StringProperty()                   # Reference to the CaseReminderHandler
    user_id = StringProperty()                      # Reference to the CommCareUser who will receive the SMS messages
    method = StringProperty(choices=METHOD_CHOICES) # See CaseReminderHandler.method
    next_fire = DateTimeProperty()                  # The date and time that the next message should go out
    last_fired = DateTimeProperty()                 # The date and time that the last message went out
    active = BooleanProperty(default=False)         # True if active, False if deactivated
    lang = StringProperty()                         # Language the reminder should be sent in
    start_date = DateProperty()                     # The date that the CaseReminder was spawned
    schedule_iteration_num = IntegerProperty()      # The current iteration through the cycle of self.handler.events
    current_event_sequence_num = IntegerProperty()  # The current event number (index to self.handler.events)
    callback_try_count = IntegerProperty()          # Keeps track of the number of times a callback has timed out
    callback_received = BooleanProperty()           # True if the expected callback was received since the last SMS was sent, False if not

    @property
    def handler(self):
        return CaseReminderHandler.get(self.handler_id)

    @property
    def current_event(self):
        return self.handler.events[self.current_event_sequence_num]

    @property
    def case(self):
        return CommCareCase.get(self.case_id)

    @property
    def user(self):
        try:
            return CommCareUser.get_by_user_id(self.user_id)
        except Exception:
            self.retire()
            return None

    def retire(self):
        self.doc_type += "-Deleted"
        self.save()
from .signals import *
