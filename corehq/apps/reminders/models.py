import pytz
from pytz import timezone
from datetime import timedelta, datetime, date, time
import re
from couchdbkit.ext.django.schema import *
from django.conf import settings
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.api import send_sms, send_sms_to_verified_number
from corehq.apps.sms.models import CallLog, EventLog, MISSED_EXPECTED_CALLBACK, CommConnectCase
from corehq.apps.users.models import CommCareUser
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
from corehq.apps.sms.util import create_task, close_task
from corehq.apps.smsforms.app import submit_unfinished_form
from corehq.apps.ivr.api import initiate_outbound_call
from dimagi.utils.couch import LockableMixIn


METHOD_CHOICES = ["sms", "email", "test", "callback", "callback_test", "survey", "ivr_survey"]

REPEAT_SCHEDULE_INDEFINITELY = -1

EVENT_AS_SCHEDULE = "SCHEDULE"
EVENT_AS_OFFSET = "OFFSET"
EVENT_INTERPRETATIONS = [EVENT_AS_SCHEDULE, EVENT_AS_OFFSET]

UI_SIMPLE_FIXED = "SIMPLE_FIXED"
UI_COMPLEX = "COMPLEX"
UI_CHOICES = [UI_SIMPLE_FIXED, UI_COMPLEX]

RECIPIENT_USER = "USER"
RECIPIENT_CASE = "CASE"
RECIPIENT_SURVEY_SAMPLE = "SURVEY_SAMPLE"
RECIPIENT_CHOICES = [RECIPIENT_USER, RECIPIENT_CASE, RECIPIENT_SURVEY_SAMPLE]

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
            else:
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
            callback_received=False,
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
            local_tmsp = datetime.combine(reminder.start_date, self.events[0].fire_time) + timedelta(days = (self.start_offset + self.events[0].day_num))
            reminder.next_fire = CaseReminderHandler.timestamp_to_utc(recipient, local_tmsp)
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
        reminder.callback_received = False
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
        iteration = 0
        while now >= reminder.next_fire and reminder.active:
            iteration += 1
            # If it is a callback reminder, check the callback_timeout_intervals
            if (reminder.method in ["callback", "callback_test", "survey"]) and len(reminder.current_event.callback_timeout_intervals) > 0:
                #reminder.callback_received is always False for surveys, so it only has an effect for callbacks
                if reminder.callback_received or reminder.callback_try_count >= len(reminder.current_event.callback_timeout_intervals):
                    if self.method == "survey" and self.submit_partial_forms and iteration > 1:
                        # This is to make sure we submit the unfinished forms even when fast-forwarding to the next event after system downtime
                        for session_id in reminder.xforms_session_ids:
                            submit_unfinished_form(session_id)
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
                next_event = reminder.current_event
                day_offset = self.start_offset + (self.schedule_length * (reminder.schedule_iteration_num - 1)) + next_event.day_num
                reminder_datetime = datetime.combine(reminder.start_date, next_event.fire_time) + timedelta(days = day_offset)
                reminder.next_fire = CaseReminderHandler.timestamp_to_utc(reminder.recipient, reminder_datetime)
            
            # Set whether or not the reminder should still be active
            reminder.active = self.get_active(reminder, reminder.next_fire, case)
    
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
        # Get the proper recipient
        recipient = reminder.recipient
        
        # Retrieve the VerifiedNumber entry for the recipient
        try:
            verified_number = recipient.get_verified_number()
        except Exception:
            verified_number = None
            
        # Get the language of the recipient
        try:
            lang = recipient.get_language_code()
        except Exception:
            lang = None
        
        if reminder.method == "ivr_survey":
            if verified_number is not None:
                initiate_outbound_call(verified_number, reminder.current_event.form_unique_id)
            return True
        elif reminder.method == "survey":
            if reminder.callback_try_count > 0:
                if self.submit_partial_forms and (reminder.callback_try_count == len(reminder.current_event.callback_timeout_intervals)):
                    for session_id in reminder.xforms_session_ids:
                        submit_unfinished_form(session_id)
                else:
                    for session_id in reminder.xforms_session_ids:
                        session = XFormsSession.view("smsforms/sessions_by_touchforms_id",
                                                        startkey=[session_id],
                                                        endkey=[session_id, {}],
                                                        include_docs=True).one()
                        if session.end_time is None:
                            vn = VerifiedNumber.view("sms/verified_number_by_owner_id",
                                                      key=session.connection_id,
                                                      include_docs=True).one()
                            if vn is not None:
                                resp = current_question(session_id)
                                send_sms_to_verified_number(vn, resp.event.text_prompt)
                return True
            else:
                recipients = []
                if self.recipient == RECIPIENT_CASE:
                    recipients = [reminder.recipient]
                elif self.recipient == RECIPIENT_SURVEY_SAMPLE:
                    recipients = [CommConnectCase.get(case_id) for case_id in reminder.recipient.contacts]
                
                reminder.xforms_session_ids = []
                
                for recipient in recipients:
                    # Close all currently open sessions
                    sessions = XFormsSession.view("smsforms/open_sessions_by_connection",
                                                 key=[reminder.domain, recipient.get_id],
                                                 include_docs=True).all()
                    for session in sessions:
                        session.end(False)
                        session.save()
                    
                    # Start the new session
                    try:
                        form_unique_id = reminder.current_event.form_unique_id
                        form = Form.get_form(form_unique_id)
                        app = form.get_app()
                        module = form.get_module()
                    except Exception as e:
                        print e
                        print "ERROR: Could not load survey form for handler " + reminder.handler_id + ", event " + str(reminder.current_event_sequence_num)
                        return False
                    session, responses = start_session(reminder.domain, recipient, app, module, form, recipient.get_id)
                    reminder.xforms_session_ids.append(session.session_id)
                    
                    # Send out first message
                    if len(responses) > 0:
                        message = format_message_list(responses)
                        verified_number = recipient.get_verified_number()
                        if len(recipients) == 1:
                            if verified_number is not None:
                                return send_sms_to_verified_number(verified_number, message)
                            else:
                                return True
                        else:
                            send_sms_to_verified_number(verified_number, message)
                    
                return True
        else:
            # If it is a callback reminder and the callback has been received, skip sending the next timeout message
            if (reminder.method == "callback" or reminder.method == "callback_test") and len(reminder.current_event.callback_timeout_intervals) > 0 and (reminder.callback_try_count > 0):
                if CallLog.inbound_call_exists(recipient.doc_type, recipient._id, reminder.last_fired):
                    reminder.callback_received = True
                    return True
                elif len(reminder.current_event.callback_timeout_intervals) == reminder.callback_try_count:
                    # On the last callback timeout, instead of sending the SMS again, log the missed callback
                    event = EventLog(
                        domain          = reminder.domain,
                        date            = self.get_now(),
                        event_type      = MISSED_EXPECTED_CALLBACK
                    )
                    if verified_number is not None:
                        event.couch_recipient_doc_type = verified_number.owner_doc_type
                        event.couch_recipient = verified_number.owner_id
                    event.save()
                    return True
            reminder.last_fired = self.get_now()
            message = reminder.current_event.message.get(lang, reminder.current_event.message[self.default_lang])
            message = Message.render(message, case=reminder.case.case_properties())
            if reminder.method == "sms" or reminder.method == "callback":
                if verified_number is not None:
                    return send_sms_to_verified_number(verified_number, message)
                elif self.recipient == RECIPIENT_USER:
                    # If there is no verified number, but the recipient is a CommCareUser, still try to send it
                    try:
                        phone_number = reminder.user.phone_number
                    except Exception:
                        # If the user has no phone number, we cannot send any SMS
                        return False
                    return send_sms(reminder.domain, reminder.user_id, phone_number, message)
                else:
                    return False
            elif reminder.method == "test" or reminder.method == "callback_test":
                print(message)
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
        
        if case.closed or case.type != self.case_type or (self.recipient == RECIPIENT_USER and not user):
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
        
        if reminder is not None and reminder.start_condition_datetime != self.start_datetime:
            reminder.retire()
            reminder = None
        
        if reminder is None:
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
    callback_received = BooleanProperty()           # True if the expected callback was received since the last SMS was sent, False if not
    start_condition_datetime = DateTimeProperty()   # The date and time matching the case property specified by the CaseReminderHandler.start_condition
    sample_id = StringProperty()
    xforms_session_ids = ListProperty(StringProperty)
    
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
        else:
            return SurveySample.get(self.sample_id)
    
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
    form_id = StringProperty()
    reminder_definitions = DictProperty() # Dictionary of SurveySample._id : CaseReminderHandler._id

class Survey(Document):
    domain = StringProperty()
    name = StringProperty()
    waves = SchemaListProperty(SurveyWave)
    followups = ListProperty(DictProperty)
    samples = ListProperty(DictProperty)
    send_automatically = BooleanProperty()
    send_followup = BooleanProperty()
    delegation_tasks = DictProperty() # Each task represented by a key-value pair of "<start_date>|<parent_case_id>|<form_unique_id>|<owner_id>" : "<subcase_id>"
    
    @classmethod
    def get_all(cls, domain):
        return cls.view('reminders/survey_by_domain',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ).all()
    
    def update_delegation_tasks(self, submitting_user_id):
        tasks_to_keep = {}
        utcnow = datetime.utcnow()
        
        # Keep unchanged tasks and create new tasks as needed
        for wave in self.waves:
            form_unique_id = wave.form_id
            for sample in self.samples:
                if sample["method"] == "CATI":
                    owner_id = sample["cati_operator"]
                    s = SurveySample.get(sample["sample_id"])
                    task_activation_datetime = CaseReminderHandler.timestamp_to_utc(s, datetime.combine(wave.date, wave.time))
                    if task_activation_datetime >= utcnow:
                        for case_id in s.contacts:
                            key = "|".join([json_format_datetime(task_activation_datetime), case_id, form_unique_id, owner_id])
                            if key in self.delegation_tasks:
                                tasks_to_keep[key] = self.delegation_tasks[key]
                            else:
                                case = CommCareCase.get(case_id)
                                tasks_to_keep[key] = create_task(case, submitting_user_id, owner_id, form_unique_id, task_activation_datetime)
        
        # Close tasks that are no longer valid
        for key, value in self.delegation_tasks.items():
            if key not in tasks_to_keep:
                data = key.split("|")
                if string_to_datetime(data[0]).replace(tzinfo=None) < utcnow:
                    tasks_to_keep[key] = value
                else:
                    close_task(self.domain, value, submitting_user_id)
        
        self.delegation_tasks = tasks_to_keep

from .signals import *
