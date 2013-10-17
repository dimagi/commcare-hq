import copy
import json
import re
from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django.core.urlresolvers import reverse
import pytz
from datetime import timedelta, datetime, time
from django.core.exceptions import ValidationError
from django.forms.fields import *
from django.forms.forms import Form
from django.forms.widgets import CheckboxSelectMultiple
from django import forms
from django.forms import Field, Widget
from corehq.apps.reminders.util import DotExpandedDict
from casexml.apps.case.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.crispy import BootstrapMultiField, FieldsetAccordionGroup, HiddenFieldWithErrors, FieldWithHelpBubble
from .models import (
    REPEAT_SCHEDULE_INDEFINITELY,
    CaseReminderEvent,
    RECIPIENT_USER,
    RECIPIENT_CASE,
    RECIPIENT_SURVEY_SAMPLE,
    RECIPIENT_OWNER,
    MATCH_EXACT,
    MATCH_REGEX,
    MATCH_ANY_VALUE,
    EVENT_AS_SCHEDULE,
    EVENT_AS_OFFSET,
    CaseReminderHandler,
    FIRE_TIME_DEFAULT,
    FIRE_TIME_CASE_PROPERTY,
    METHOD_SMS,
    METHOD_SMS_CALLBACK,
    METHOD_SMS_SURVEY,
    METHOD_IVR_SURVEY,
    CASE_CRITERIA,
    QUESTION_RETRY_CHOICES,
    FORM_TYPE_ONE_BY_ONE,
    FORM_TYPE_ALL_AT_ONCE,
    SurveyKeyword,
    RECIPIENT_PARENT_CASE,
    RECIPIENT_SUBCASE,
    FIRE_TIME_RANDOM,
    ON_DATETIME,
    SEND_NOW,
    SEND_LATER,
    RECIPIENT_USER_GROUP,
    UI_SIMPLE_FIXED,
    UI_COMPLEX,
)
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from dateutil.parser import parse
from dimagi.utils.excel import WorkbookJSONReader, WorksheetNotFound
from openpyxl.shared.exc import InvalidFileException
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.models import Form as CCHQForm
from dimagi.utils.django.fields import TrimmedCharField
from corehq.apps.reports import util as report_utils
from dimagi.utils.timezones import utils as tz_utils

YES_OR_NO = (
    ("Y","Yes"),
    ("N","No"),
)

NOW_OR_LATER = (
    (SEND_NOW, _("Now")),
    (SEND_LATER ,_("Later")),
)

CONTENT_CHOICES = (
    (METHOD_SMS, _("SMS Message")),
    (METHOD_SMS_SURVEY, _("SMS Form Interaction")),
)

ONE_TIME_RECIPIENT_CHOICES = (
    ("", _("---choose---")),
    (RECIPIENT_SURVEY_SAMPLE, _("Case Group")),
    (RECIPIENT_USER_GROUP, _("User Group")),
)

METHOD_CHOICES = (
    ('sms', 'SMS'),
    #('email', 'Email'),
    #('test', 'Test'),
    ('survey', 'SMS survey'),
    ('callback', 'SMS expecting callback'),
    ('ivr_survey', 'IVR survey'),
)

RECIPIENT_CHOICES = (
    (RECIPIENT_OWNER, "The case's owner(s)"),
    (RECIPIENT_USER, "The case's last submitting user"),
    (RECIPIENT_CASE, "The case"),
    (RECIPIENT_PARENT_CASE, "The case's parent case"),
    (RECIPIENT_SUBCASE, "The case's child case(s)"),
    (RECIPIENT_SURVEY_SAMPLE, "Survey Sample"),
)

MATCH_TYPE_DISPLAY_CHOICES = (
    (MATCH_EXACT, "equals"),
    (MATCH_ANY_VALUE, "exists"),
    (MATCH_REGEX, "matches the regular expression")
)

START_IMMEDIATELY = "IMMEDIATELY"
START_ON_DATE = "DATE"

START_CHOICES = (
    (START_ON_DATE, "defined by case property"),
    (START_IMMEDIATELY, "immediately")
)

ITERATE_INDEFINITELY = "INDEFINITE"
ITERATE_FIXED_NUMBER = "FIXED"

ITERATION_CHOICES = (
    (ITERATE_INDEFINITELY, "using the following case property"),
    (ITERATE_FIXED_NUMBER, "after repeating the schedule the following number of times")
)

EVENT_CHOICES = (
    (EVENT_AS_OFFSET, "Offset-based"),
    (EVENT_AS_SCHEDULE, "Schedule-based")
)

FORM_TYPE_CHOICES = (
    (FORM_TYPE_ONE_BY_ONE, "One sms per question"),
    (FORM_TYPE_ALL_AT_ONCE, "All questions in one sms"),
)

def validate_date(value):
    date_regex = re.compile("^\d\d\d\d-\d\d-\d\d$")
    if date_regex.match(value) is None:
        raise ValidationError("Dates must be in yyyy-mm-dd format.")

def validate_time(value):
    time_regex = re.compile("^\d{1,2}:\d\d(:\d\d){0,1}$")
    if time_regex.match(value) is None:
        raise ValidationError("Times must be in hh:mm format.")

def validate_form_unique_id(form_unique_id, domain):
    try:
        form = CCHQForm.get_form(form_unique_id)
        app = form.get_app()
        assert app.domain == domain
    except Exception:
        raise ValidationError(_("Invalid form chosen."))

# Used for validating the phone number from a UI. Returns the phone number if valid, otherwise raises a ValidationError.
def validate_phone_number(value):
    error_msg = _("Phone numbers must consist only of digits and must be in international format.")
    if not isinstance(value, basestring):
        # Cast to an int, then a str. Needed for excel upload where the field comes back as a float.
        try:
            value = str(int(value))
        except Exception:
            raise ValidationError(error_msg)
    
    value = value.strip()
    phone_regex = re.compile("^\d+$")
    if phone_regex.match(value) is None:
        raise ValidationError(error_msg)
    
    if isinstance(value, unicode):
        value = str(value)
    
    return value

class CaseReminderForm(Form):
    """
    A form used to create/edit fixed-schedule CaseReminderHandlers.
    """
    nickname = CharField()
    case_type = CharField()
#    method = ChoiceField(choices=METHOD_CHOICES)
    default_lang = CharField()
    message = CharField()
    start = CharField()
    start_offset = IntegerField()
    frequency = IntegerField()
    until = CharField()

    def clean_message(self):
        try:
            message = json.loads(self.cleaned_data['message'])
        except ValueError:
            raise ValidationError('Message has to be a JSON obj')
        if not isinstance(message, dict):
            raise ValidationError('Message has to be a JSON obj')
        return message

class EventWidget(Widget):
    
    def value_from_datadict(self, data, files, name, *args, **kwargs):
        reminder_events_raw = {}
        for key in data:
            if key[0:16] == "reminder_events.":
                reminder_events_raw[key] = data[key]
        
        event_dict = DotExpandedDict(reminder_events_raw)
        events = []
        if len(event_dict) > 0:
            for key in sorted(event_dict["reminder_events"].iterkeys(), key=lambda a : int(a)):
                events.append(event_dict["reminder_events"][key])
        
        return events

class EventListField(Field):
    required = None
    label = None
    initial = None
    widget = None
    help_text = None
    
    def __init__(self, required=True, label="", initial=[], widget=EventWidget(), help_text="", *args, **kwargs):
        self.required = required
        self.label = label
        self.initial = initial
        self.widget = widget
        self.help_text = help_text
    
    def clean(self, value):
        # See clean_events() method in the form for validation
        return value

class ComplexCaseReminderForm(Form):
    """
    A form used to create/edit CaseReminderHandlers with any type of schedule.
    """
    active = BooleanField(required=False)
    nickname = CharField(error_messages={"required":"Please enter the name of this reminder definition."})
    start_condition_type = CharField()
    case_type = CharField(required=False)
    method = ChoiceField(choices=METHOD_CHOICES)
    recipient = ChoiceField(choices=RECIPIENT_CHOICES)
    start_match_type = ChoiceField(choices=MATCH_TYPE_DISPLAY_CHOICES)
    start_choice = ChoiceField(choices=START_CHOICES)
    iteration_type = ChoiceField(choices=ITERATION_CHOICES)
    start_property = CharField(required=False)
    start_value = CharField(required=False)
    start_date = CharField(required=False)
    start_offset = CharField(required=False)
    use_until = CharField()
    until = CharField(required=False)
    default_lang = CharField(required=False)
    max_iteration_count_input = CharField(required=False)
    max_iteration_count = IntegerField(required=False)
    event_interpretation = ChoiceField(choices=EVENT_CHOICES)
    schedule_length = CharField()
    events = EventListField()
    submit_partial_forms = BooleanField(required=False)
    include_case_side_effects = BooleanField(required=False)
    start_datetime_date = CharField(required=False)
    start_datetime_time = CharField(required=False)
    frequency = CharField()
    sample_id = CharField(required=False)
    enable_advanced_time_choices = BooleanField(required=False)
    max_question_retries = ChoiceField(choices=((n,n) for n in QUESTION_RETRY_CHOICES))
    recipient_case_match_property = CharField(required=False)
    recipient_case_match_type = ChoiceField(choices=MATCH_TYPE_DISPLAY_CHOICES,required=False)
    recipient_case_match_value = CharField(required=False)
    force_surveys_to_use_triggered_case = BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(ComplexCaseReminderForm, self).__init__(*args, **kwargs)
        if "initial" in kwargs:
            initial = kwargs["initial"]
        else:
            initial = {}
        
        # Populate iteration_type and max_iteration_count_input
        if "max_iteration_count" in initial:
            if initial["max_iteration_count"] == REPEAT_SCHEDULE_INDEFINITELY:
                self.initial["iteration_type"] = "INDEFINITE"
                self.initial["max_iteration_count_input"] = ""
            else:
                self.initial["iteration_type"] = "FIXED"
                self.initial["max_iteration_count_input"] = initial["max_iteration_count"]
        else:
            self.initial["iteration_type"] = "INDEFINITE"
            self.initial["max_iteration_count_input"] = ""
        
        # Populate start_choice
        if initial.get("start_choice", None) is None:
            if initial.get("start_date", None) is None:
                self.initial["start_choice"] = START_IMMEDIATELY
            else:
                self.initial["start_choice"] = START_ON_DATE
        
        enable_advanced_time_choices = False
        # Populate events
        events = []
        if "events" in initial:
            for e in initial["events"]:
                ui_event = {
                    "day"       : e.day_num,
                    "time"      : e.fire_time_aux if e.fire_time_type == FIRE_TIME_CASE_PROPERTY else "%02d:%02d" % (e.fire_time.hour, e.fire_time.minute),
                    "time_type" : e.fire_time_type,
                    "time_window_length" : e.time_window_length,
                }
                
                if e.fire_time_type != FIRE_TIME_DEFAULT:
                    enable_advanced_time_choices = True
                
                messages = {}
                counter = 1
                for key, value in e.message.items():
                    messages[str(counter)] = {"language" : key, "text" : value}
                    counter += 1
                ui_event["messages"] = messages
                
                timeouts_str = []
                for t in e.callback_timeout_intervals:
                    timeouts_str.append(str(t))
                ui_event["timeouts"] = ",".join(timeouts_str)
                
                ui_event["survey"] = e.form_unique_id
                
                events.append(ui_event)
        
        self.initial["events"] = events
        self.initial["enable_advanced_time_choices"] = enable_advanced_time_choices
    
    def clean_max_iteration_count(self):
        if self.cleaned_data.get("iteration_type") == ITERATE_FIXED_NUMBER:
            max_iteration_count = self.cleaned_data.get("max_iteration_count_input")
            try:
                max_iteration_count = int(max_iteration_count)
                assert max_iteration_count > 0
                return max_iteration_count
            except (ValueError, AssertionError):
                raise ValidationError("Please enter a number greater than zero.")
        else:
            return REPEAT_SCHEDULE_INDEFINITELY
    
    def clean_case_type(self):
        if self.cleaned_data.get("start_condition_type") == CASE_CRITERIA:
            value = self.cleaned_data.get("case_type").strip()
            if value == "":
                raise ValidationError("Please enter the case type.")
            return value
        else:
            return None
    
    def clean_start_property(self):
        if self.cleaned_data.get("start_condition_type") == CASE_CRITERIA:
            value = self.cleaned_data.get("start_property").strip()
            if value == "":
                raise ValidationError("Please enter the case property's name.")
            return value
        else:
            return None
    
    def clean_start_match_type(self):
        if self.cleaned_data.get("start_condition_type") == CASE_CRITERIA:
            return self.cleaned_data.get("start_match_type")
        else:
            return None
    
    def clean_start_value(self):
        if self.cleaned_data.get("start_match_type", None) == MATCH_ANY_VALUE or self.cleaned_data.get("start_condition_type") != CASE_CRITERIA:
            return None
        else:
            value = self.cleaned_data.get("start_value").strip()
            if value == "":
                raise ValidationError("Please enter the value to match.")
            return value
    
    def clean_start_date(self):
        if self.cleaned_data.get("start_choice", None) == START_IMMEDIATELY or self.cleaned_data.get("start_condition_type") != CASE_CRITERIA:
            return None
        else:
            value = self.cleaned_data.get("start_date").strip()
            if value is None or value == "":
                raise ValidationError("Please enter the name of the case property.")
            return value
    
    def clean_start_offset(self):
        if self.cleaned_data.get("start_condition_type") == CASE_CRITERIA:
            value = self.cleaned_data.get("start_offset").strip()
            try:
                value = int(value)
                return value
            except ValueError:
                raise ValidationError("Please enter an integer.")
        else:
            return 0
    
    def clean_until(self):
        if self.cleaned_data.get("use_until", None) == "N" or self.cleaned_data.get("start_condition_type") != CASE_CRITERIA:
            return None
        else:
            value = self.cleaned_data.get("until").strip()
            if value == "":
                raise ValidationError("Please enter the name of the case property.")
            return value
    
    def clean_default_lang(self):
        if self.cleaned_data.get("method") in ["sms", "callback"]:
            value = self.cleaned_data.get("default_lang").strip()
            if value == "":
                raise ValidationError("Please enter the default language code to use for the messages.")
            return value
        else:
            return None
    
    def clean_start_datetime_date(self):
        if self.cleaned_data.get("start_condition_type") == ON_DATETIME:
            value = self.cleaned_data.get("start_datetime_date")
            validate_date(value)
            return value
        else:
            return None
    
    def clean_start_datetime_time(self):
        if self.cleaned_data.get("start_condition_type") == ON_DATETIME:
            value = self.cleaned_data.get("start_datetime_time")
            validate_time(value)
            return value
        else:
            return None
    
    def clean_sample_id(self):
        if self.cleaned_data.get("recipient") == RECIPIENT_SURVEY_SAMPLE:
            value = self.cleaned_data.get("sample_id")
            if value is None or value == "":
                raise ValidationError("Please select a Survey Sample.")
            return value
        else:
            return None
    
    def clean_schedule_length(self):
        try:
            value = self.cleaned_data.get("schedule_length")
            value = int(value)
        except ValueError:
            raise ValidationError("Please enter a number.")
        
        if self.cleaned_data.get("event_interpretation") == EVENT_AS_OFFSET and value < 0:
            raise ValidationError("Please enter a non-negative number.")
        elif self.cleaned_data.get("event_interpretation") == EVENT_AS_SCHEDULE and value <= 0:
            raise ValidationError("Please enter a positive number.")
        
        return value
    
    def clean_max_question_retries(self):
        # Django already validates that it's in the list of choices, just cast it to an int
        return int(self.cleaned_data["max_question_retries"])
    
    def clean_events(self):
        value = self.cleaned_data.get("events")
        method = self.cleaned_data.get("method")
        event_interpretation = self.cleaned_data.get("event_interpretation")
        start_condition_type = self.cleaned_data.get("start_condition_type")
        enable_advanced_time_choices = self.cleaned_data.get("enable_advanced_time_choices")
        events = []
        has_fire_time_case_property = False
        max_day = 0
        for e in value:
            try:
                day = int(e["day"])
                assert day >= 0
                if day > max_day:
                    max_day = day
            except (ValueError, AssertionError):
                raise ValidationError("Day must be specified and must be a non-negative number.")
            
            if enable_advanced_time_choices and start_condition_type == CASE_CRITERIA and event_interpretation == EVENT_AS_SCHEDULE:
                fire_time_type = e["time_type"]
            else:
                fire_time_type = FIRE_TIME_DEFAULT
            
            if fire_time_type == FIRE_TIME_CASE_PROPERTY:
                has_fire_time_case_property = True
                time = None
                fire_time_aux = e["time"].strip()
                if len(fire_time_aux) == 0:
                    raise ValidationError("Please enter the case property from which to pull the time.")
            else:
                validate_time(e["time"])
                try:
                    time = parse(e["time"]).time()
                except Exception:
                    raise ValidationError("Please enter a valid time from 00:00 to 23:59.")
                fire_time_aux = None
            
            if fire_time_type == FIRE_TIME_RANDOM:
                try:
                    time_window_length = int(e["time_window_length"])
                    assert time_window_length > 0 and time_window_length < 1440
                except (ValueError, AssertionError):
                    raise ValidationError(_("Window length must be greater than 0 and less than 1440"))
            else:
                time_window_length = None
            
            message = {}
            if method in [METHOD_SMS, METHOD_SMS_CALLBACK]:
                for key in e["messages"]:
                    language = e["messages"][key]["language"].strip()
                    text = e["messages"][key]["text"].strip()
                    if len(language) == 0:
                        raise ValidationError("Please enter a language code.")
                    if len(text) == 0:
                        raise ValidationError("Please enter a message.")
                    if language in message:
                        raise ValidationError("You have entered the same language twice for the same reminder event.");
                    message[language] = text
            
            if len(e["timeouts"].strip()) == 0 or method not in [METHOD_SMS_CALLBACK, METHOD_SMS_SURVEY, METHOD_IVR_SURVEY]:
                timeouts_int = []
            else:
                timeouts_str = e["timeouts"].split(",")
                timeouts_int = []
                for t in timeouts_str:
                    try:
                        t = int(t)
                        assert t > 0
                        timeouts_int.append(t)
                    except (ValueError, AssertionError):
                        raise ValidationError("Timeout intervals must be a list of positive numbers separated by commas.")
            
            form_unique_id = None
            if method in [METHOD_SMS_SURVEY, METHOD_IVR_SURVEY]:
                form_unique_id = e.get("survey", None)
                if form_unique_id is None:
                    raise ValidationError("Please create a form for the survey first, and then create the reminder definition.")
            
            events.append(CaseReminderEvent(
                day_num = day,
                fire_time = time,
                message = message,
                callback_timeout_intervals = timeouts_int,
                form_unique_id = form_unique_id,
                fire_time_type = fire_time_type,
                fire_time_aux = fire_time_aux,
                time_window_length = time_window_length,
            ))
        
        min_schedule_length = max_day + 1
        if event_interpretation == EVENT_AS_SCHEDULE and self.cleaned_data.get("schedule_length") < min_schedule_length:
            raise ValidationError(_("Schedule length must be at least %(min_schedule_length)s according to the current event schedule.") % {"min_schedule_length" : min_schedule_length})
        
        if len(events) == 0:
            raise ValidationError("You must have at least one reminder event.")
        else:
            if event_interpretation == EVENT_AS_SCHEDULE and not has_fire_time_case_property:
                events.sort(key=lambda e : ((1440 * e.day_num) + (60 * e.fire_time.hour) + e.fire_time.minute))
        
        return events
    
    def clean_recipient_case_match_property(self):
        if self.cleaned_data.get("recipient") == RECIPIENT_SUBCASE:
            value = self.cleaned_data.get("recipient_case_match_property")
            if value is not None:
                value = value.strip()
            if value is None or value == "":
                raise ValidationError(_("Please enter a case property name."))
            return value
        else:
            return None
    
    def clean_recipient_case_match_type(self):
        if self.cleaned_data.get("recipient") == RECIPIENT_SUBCASE:
            return self.cleaned_data.get("recipient_case_match_type")
        else:
            return None
    
    def clean_recipient_case_match_value(self):
        if self.cleaned_data.get("recipient") == RECIPIENT_SUBCASE and self.cleaned_data.get("recipient_case_match_type") in [MATCH_EXACT, MATCH_REGEX]:
            value = self.cleaned_data.get("recipient_case_match_value")
            if value is not None:
                value = value.strip()
            if value is None or value == "":
                raise ValidationError(_("Please enter a value to match."))
            return value
        else:
            return None
    
    def clean(self):
        cleaned_data = super(ComplexCaseReminderForm, self).clean()
        
        # Do validation on schedule length and minimum intraday ticks
        
        events = cleaned_data.get("events")
        iteration_type = cleaned_data.get("iteration_type")
        max_iteration_count = cleaned_data.get("max_iteration_count")
        schedule_length = cleaned_data.get("schedule_length")
        event_interpretation = cleaned_data.get("event_interpretation")
        
        if (events is not None) and (iteration_type is not None) and (max_iteration_count is not None) and (schedule_length is not None) and (event_interpretation is not None):
            if event_interpretation == EVENT_AS_SCHEDULE:
                if schedule_length < 1:
                    self._errors["schedule_length"] = self.error_class(["Schedule length must be greater than 0."])
                    del cleaned_data["schedule_length"]
            else:
                if schedule_length < 0:
                    self._errors["schedule_length"] = self.error_class(["Days to wait cannot be a negative number."])
                    del cleaned_data["schedule_length"]
                elif (max_iteration_count != 1) and (schedule_length == 0):
                    first = True
                    minimum_tick = None
                    for e in events:
                        if first:
                            minimum_tick = timedelta(days = e.day_num, hours = e.fire_time.hour, minutes = e.fire_time.minute)
                            first = False
                        else:
                            this_tick = timedelta(days = e.day_num, hours = e.fire_time.hour, minutes = e.fire_time.minute)
                            if this_tick < minimum_tick:
                                minimum_tick = this_tick
                    if minimum_tick < timedelta(hours = 1):
                        self._errors["events"] = self.error_class(["Minimum tick for a schedule repeated multiple times intraday is 1 hour."])
                        del cleaned_data["events"]
        
        # Ensure that there is a translation for the default language
        
        default_lang = cleaned_data.get("default_lang")
        method = cleaned_data.get("method")
        events = cleaned_data.get("events")
        
        if (default_lang is not None) and (method is not None) and (events is not None):
            if (method == "sms" or method == "callback"):
                for e in events:
                    if default_lang not in e.message:
                        self._errors["events"] = self.error_class(["Every message must contain a translation for the default language."])
                        del cleaned_data["events"]
                        break
        
        return cleaned_data


MATCH_TYPE_CHOICES = (
    (MATCH_ANY_VALUE, "exists."),
    (MATCH_EXACT, "equals"),
    (MATCH_REGEX, "matches regular expression"),
)

START_REMINDER_ON_CASE_DATE = 'case_date'
START_REMINDER_ON_CASE_PROPERTY = 'case_property'

START_DATE_OFFSET_BEFORE = 'offset_before'
START_DATE_OFFSET_AFTER = 'offset_after'

START_PROPERTY_OFFSET_DELAY = 'offset_delay'
START_PROPERTY_OFFSET_IMMEDIATE = 'offset_immediate'

EVENT_TIMING_IMMEDIATE = 'immediate'

REPEAT_TYPE_NO = 'no_repeat'
REPEAT_TYPE_INDEFINITE = 'indefinite'
REPEAT_TYPE_SPECIFIC = 'specific'

STOP_CONDITION_CASE_PROPERTY = 'case_property'


class SimpleScheduleCaseReminderForm(forms.Form):
    """
    This form creates a new CaseReminder. It is the most basic version, no advanced options (like language).
    """
    nickname = forms.CharField(
        label="Name",
        error_messages={
            'required': "Please enter a name for this reminder",
        }
    )
    active = forms.BooleanField(
        required=False,
        initial=True,
        label="This reminder is active."
    )

    # Fieldset: Send Options
    # simple has start_condition_type = CASE_CRITERIA by default
    case_type = forms.CharField(
        required=False,
        label="Case Type",
    )
    start_reminder_on = forms.ChoiceField(
        label="Start Reminder",
        required=False,
        choices=(
            (START_REMINDER_ON_CASE_DATE, "on a date specified in the Case"),
            (START_REMINDER_ON_CASE_PROPERTY, "when the Case is in the following state"),
        ),
    )
    ## send options > start_reminder_on = case_date
    start_property = forms.CharField(
        required=False,
        label="Enter a Case Property",
    )
    start_match_type = forms.ChoiceField(
        required=False,
        choices=MATCH_TYPE_CHOICES,
    )
    # only shows up if start_match_type != MATCH_ANY_VALUE
    start_value = forms.CharField(
        required=False,
        label="Value"
    )
    # this is a UI control that determines how start_offset is calculated (0 or an integer)
    start_property_offset_type = forms.ChoiceField(
        required=False,
        choices=(
            (START_PROPERTY_OFFSET_DELAY, "Delay By"),
            (START_PROPERTY_OFFSET_IMMEDIATE, "Immediately"),
        )
    )
    # becomes start_offset
    start_property_offset = forms.IntegerField(
        required=False,
        initial=1,
    )
    ## send options > start_reminder_on = case_property
    start_date = forms.CharField(
        required=False,
        label="Case Property",
    )
    start_date_offset_type = forms.ChoiceField(
        required=False,
        choices=(
            (START_DATE_OFFSET_BEFORE, "Before Date By"),
            (START_DATE_OFFSET_AFTER, "After Date By"),
        )
    )
    # becomes start_offset
    start_date_offset = forms.IntegerField(
        required=False,
        initial=0,
    )

    # Fieldset: Recipient
    recipient = forms.ChoiceField(
        choices=(
            (RECIPIENT_CASE, "Case"),
            (RECIPIENT_OWNER, "Case Owner"),
            (RECIPIENT_USER, "User Last Modifying Case"),
            (RECIPIENT_PARENT_CASE, "Case's Parent Case"),
            (RECIPIENT_SUBCASE, "Case's Child Cases"),
        ),
    )
    ## recipient = RECIPIENT_SUBCASE
    recipient_case_match_property = forms.CharField(
        label="Case Property",
        required=False
    )
    recipient_case_match_type = forms.ChoiceField(
        required=False,
        choices=MATCH_TYPE_CHOICES,
    )
    recipient_case_match_value = forms.CharField(
        label="Value",
        required=False
    )

    # Fieldset: Message Content
    method = forms.ChoiceField(
        label="Send",
        choices=(
            (METHOD_SMS, "SMS"),
            (METHOD_SMS_SURVEY, "SMS Survey"),
        ),
    )
    # contains a string-ified JSON object of events
    events = forms.CharField(
        required=False,
        widget=forms.HiddenInput
    )

    event_timing = forms.ChoiceField(
        label="Timing",
    )

    event_interpretation = forms.ChoiceField(
        label="Schedule Type",
        initial=EVENT_AS_OFFSET,
        choices=(
            (EVENT_AS_OFFSET, "Offset-based"),
            (EVENT_AS_SCHEDULE, "Schedule-based"),
        ),
        widget=forms.HiddenInput  # validate as choice, but don't show the widget.
    )

    # Fieldset: Repeat
    repeat_type = forms.ChoiceField(
        required=False,
        label="Repeat Reminder",
        initial=REPEAT_TYPE_NO,
        choices=(
            (REPEAT_TYPE_NO, "No"),  # reminder_type = ONE_TIME
            (REPEAT_TYPE_INDEFINITE, "Indefinitely"),  # reminder_type = DEFAULT, max_iteration_count = -1
            (REPEAT_TYPE_SPECIFIC, "Specific Number of Times"),
        )
    )
    # shown if repeat_type != 'no_repeat'
    schedule_length = forms.IntegerField(
        required=False,
        label="Repeat Every",
    )
    # shown if repeat_type == 'specific' (0 if no_repeat, -1 if indefinite)
    max_iteration_count = forms.IntegerField(
        required=False,
        label="Number of Times",
    )
    # shown if repeat_type != 'no_repeat'
    stop_condition = forms.ChoiceField(
        required=False,
        label="",
        choices=(
            ('', '(none)'),
            (STOP_CONDITION_CASE_PROPERTY, 'On Date in Case'),
        )
    )
    until = forms.CharField(
        required=False,
        label="Enter a Case Property",
    )

    # Advanced Toggle
    submit_partial_forms = forms.BooleanField(
        required=False,
        label="Submit Partial Forms",
    )
    include_case_side_effects = forms.BooleanField(
        required=False,
        label="Include Case Changes for Partial Forms",
    )
    default_lang = forms.ChoiceField(
        required=False,
        label="Default Language",
        choices=(
            ('en', "English (en)"),
        )
    )
    # only show if SMS_SURVEY or IVR_SURVEY is chosen
    max_question_retries = forms.ChoiceField(
        required=False,
        choices=((n, n) for n in QUESTION_RETRY_CHOICES)
    )

    def __init__(self, data=None, is_previewer=False, domain=None, ui_type=None, *args, **kwargs):
        if 'initial' not in kwargs:
            kwargs['initial'] = {
                'event_timing': self._format_event_timing_choice(EVENT_AS_OFFSET,
                                                                 FIRE_TIME_DEFAULT, EVENT_TIMING_IMMEDIATE),
                'events': json.dumps([{
                    'day_num': 0,
                    'fire_time_type': FIRE_TIME_DEFAULT,
                    'message': {
                        'en': "",
                    },
                }])
            }

        super(SimpleScheduleCaseReminderForm, self).__init__(data, *args, **kwargs)

        self.domain = domain
        self.ui_type = ui_type

        if is_previewer:
            method_choices = copy.copy(self.fields['method'].choices)
            method_choices.extend([
                (METHOD_IVR_SURVEY, "IVR Survey"),
                (METHOD_SMS_CALLBACK, "SMS Expecting Callback"),
            ])
            self.fields['method'].choices = method_choices

        event_timing_choices = (
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, EVENT_TIMING_IMMEDIATE), "Immediately"),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_DEFAULT, None), "At a Specific Time"),
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, None), "Delay After Start"),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_CASE_PROPERTY, None), "Time in Case"),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_RANDOM, None), "Random Time"),
        )
        event_timing_choices = [(self._format_event_timing_choice(e[0][0], e[0][1], e[0][2]), e[1])
                                for e in event_timing_choices]
        self.fields['event_timing'].choices = event_timing_choices

        start_section = crispy.Fieldset(
            'Start',
            crispy.Field(
                'case_type',
                css_class="input-large",
                data_bind="value: case_type",
                data_placeholder="Enter a Case Type"
            ),
            FieldWithHelpBubble(
                'start_reminder_on',
                data_bind="value: start_reminder_on",
                css_class="input-xlarge",
                help_bubble_text=("Reminders can either start based on a date in a case property "
                                  "or if the case is in a particular state (ex: case property 'high_risk' "
                                  "is equal to 'yes')")
            ),
            crispy.Div(
                BootstrapMultiField(
                    "When Case Property",
                    InlineField(
                        'start_property',
                        css_class="input-large",
                    ),
                    InlineField(
                        'start_match_type',
                        data_bind="value: start_match_type",
                    ),
                    InlineField(
                        'start_value',
                        style="margin-left: 5px;",
                        data_bind="visible: isStartMatchValueVisible",
                    ),
                ),
                BootstrapMultiField(
                    "Begin Sending",
                    InlineField(
                        'start_property_offset_type',
                        data_bind="value: start_property_offset_type",
                    ),
                    InlineField(
                        'start_property_offset',
                        css_class='input-mini',
                        style="margin-left: 5px;",
                        data_bind="visible: isStartPropertyOffsetVisible",
                    ),
                    crispy.Div(
                        crispy.HTML('day(s)'),
                        css_class="help-inline",
                        data_bind="visible: isStartPropertyOffsetVisible",
                    ),
                ),
                data_bind="visible: isStartReminderCaseProperty"
            ),
            crispy.Div(
                crispy.Field(
                    'start_date',
                    data_placeholder="Enter a Case Property",
                    css_class="input-large",
                ),
                BootstrapMultiField(
                    "",
                    InlineField('start_date_offset_type'),
                    crispy.Div(
                        InlineField(
                            'start_date_offset',
                            css_class='input-mini',

                        ),
                        crispy.HTML('<p class="help-inline">day(s)</p>'),
                        style='display: inline; margin-left: 5px;'
                    )
                ),
                data_bind="visible: isStartReminderCaseDate"
            ),
            BootstrapMultiField(
                "Time",
                InlineField('event_timing', data_bind="value: event_timing"),
                crispy.Div(
                    style="display: inline;",
                    data_bind="template: {name: 'event-fire-template', foreach: eventObjects}"
                ),
                css_id="timing_block",
                help_bubble_text=("This controls when the message will be sent. The Time in Case "
                                  "option is useful, for example, if the recipient has chosen a "
                                  "specific time to receive the message.")
            ),
            crispy.Div(
                style="display: inline;",
                data_bind="template: {name: 'event-general-template', foreach: eventObjects}"
            ),
        )

        recipient_section = crispy.Fieldset(
            "Recipient",
            FieldWithHelpBubble(
                'recipient',
                data_bind="value: recipient",
                help_bubble_text=("The contact related to the case that reminder should go to.  The Case "
                                  "Owners are any mobile workers for which the case appears on their phone. "
                                  "For cases with child or parent cases, you can also send the message to those "
                                  "contacts. ")
            ),
            BootstrapMultiField(
                "When Case Property",
                InlineField(
                    'recipient_case_match_property',
                    placeholder="Enter a Case Property",
                    css_class="input-large",
                ),
                InlineField(
                    'recipient_case_match_type',
                    data_bind="value: recipient_case_match_type",
                ),
                InlineField(
                    'recipient_case_match_value',
                    data_bind="visible: isRecipientCaseValueVisible",
                ),
                data_bind="visible: isRecipientSubcase",
            ),
        )

        message_section = crispy.Fieldset(
            "Message Content",
            FieldWithHelpBubble(
                'method',
                data_bind="value: method",
                help_bubble_text=("Send a single SMS message or an interactive SMS survey. "
                                  "SMS surveys are designed in the Surveys or Application "
                                  "section. ")
            ),
            crispy.Field('event_interpretation', data_bind="value: event_interpretation"),
            HiddenFieldWithErrors('events', data_bind="value: events"),
            crispy.Div(data_bind="template: {name: 'event-template', foreach: eventObjects}"),
        )

        repeat_section = crispy.Fieldset(
            "Repeat",
            crispy.Field('repeat_type', data_bind="value: repeat_type"),
            crispy.Div(
                crispy.Field('max_iteration_count'),
                data_bind="visible: isMaxIterationCountVisible",
            ),
            BootstrapMultiField(
                "Repeat Every",
                InlineField('schedule_length'),
                crispy.HTML('<p class="help-inline">day(s)</p>'),
                data_bind="visible: isScheduleLengthVisible",
            ),
            BootstrapMultiField(
                "Stop Condition",
                InlineField('stop_condition', data_bind="value: stop_condition"),
                crispy.Div(
                    InlineField(
                        'until',
                        css_class="input-large",
                    ),
                    css_class="help-inline",
                    data_bind="visible: isUntilVisible",
                ),
                data_bind="visible: isStopConditionVisible",
            )
        )

        advanced_section = FieldsetAccordionGroup(
            "Advanced Options",
            BootstrapMultiField(
                "Default Language",
                InlineField(
                    'default_lang',
                    data_bind="options: available_languages, "
                              "value: default_lang, "
                              "optionsText: 'name', optionsValue: 'langcode'",
                ),
                crispy.HTML('<a href="#add-language-modal" '
                            'class="btn btn-primary" style="margin-left: 5px;" '
                            'data-toggle="modal">Add Language</a>'),
            ),
            crispy.Div(
                style="display: inline;",
                data_bind="template: {name: 'event-timeouts-template', foreach: eventObjects}"
            ),
            crispy.Div(
                'max_question_retries',
                data_bind="visible: isMaxQuestionRetriesVisible",
            ),
            'submit_partial_forms',
            'include_case_side_effects',
            active=False,
        )

        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Field('nickname'),
            crispy.Field('active'),
            start_section,
            recipient_section,
            message_section,
            repeat_section,
            advanced_section,
            FormActions(
                StrictButton(
                    "Create Reminder",
                    css_class='btn-primary',
                    type='submit',
                ),
                crispy.HTML('<a href="%s" class="btn">Cancel</a>' % reverse('list_reminders', args=[self.domain]))
            )
        )

    @property
    def current_values(self):
        current_values = {}
        for field_name in self.fields.keys():
            current_values[field_name] = self[field_name].value()
        return current_values

    @property
    def select2_fields(self):
        case_properties = [
            'start_property',
            'start_date',
            'until',
            'fire_time_aux',
        ]
        subcase_properties = [
            'recipient_case_match_property',
        ]

        _fmt_field = lambda name, action: {'name': name, 'action': action}
        return ([_fmt_field('case_type', 'search_case_type')] +
                [_fmt_field(cp, 'search_case_property') for cp in case_properties] +
                [_fmt_field(sp, 'search_subcase_property') for sp in subcase_properties])

    @property
    def relevant_choices(self):
        return {
            'MATCH_ANY_VALUE': MATCH_ANY_VALUE,
            'START_REMINDER_ON_CASE_PROPERTY': START_REMINDER_ON_CASE_PROPERTY,
            'START_REMINDER_ON_CASE_DATE': START_REMINDER_ON_CASE_DATE,
            'RECIPIENT_CASE': RECIPIENT_CASE,
            'RECIPIENT_SUBCASE': RECIPIENT_SUBCASE,
            'METHOD_SMS': METHOD_SMS,
            'METHOD_SMS_CALLBACK': METHOD_SMS_CALLBACK,
            'METHOD_SMS_SURVEY': METHOD_SMS_SURVEY,
            'METHOD_IVR_SURVEY': METHOD_IVR_SURVEY,
            'START_PROPERTY_OFFSET_DELAY': START_PROPERTY_OFFSET_DELAY,
            'START_PROPERTY_OFFSET_IMMEDIATE': START_PROPERTY_OFFSET_IMMEDIATE,
            'FIRE_TIME_DEFAULT': FIRE_TIME_DEFAULT,
            'FIRE_TIME_CASE_PROPERTY': FIRE_TIME_CASE_PROPERTY,
            'FIRE_TIME_RANDOM': FIRE_TIME_RANDOM,
            'EVENT_AS_OFFSET': EVENT_AS_OFFSET,
            'EVENT_AS_SCHEDULE': EVENT_AS_SCHEDULE,
            'UI_SIMPLE_FIXED': UI_SIMPLE_FIXED,
            'UI_COMPLEX': UI_COMPLEX,
            'EVENT_TIMING_IMMEDIATE': EVENT_TIMING_IMMEDIATE,
            'REPEAT_TYPE_NO': REPEAT_TYPE_NO,
            'REPEAT_TYPE_INDEFINITE': REPEAT_TYPE_INDEFINITE,
            'REPEAT_TYPE_SPECIFIC': REPEAT_TYPE_SPECIFIC,
            'STOP_CONDITION_CASE_PROPERTY': STOP_CONDITION_CASE_PROPERTY,
        }

    @staticmethod
    def _format_event_timing_choice(event_interpretation, fire_time_type, special=None):
        return json.dumps({
            'event_interpretation': event_interpretation,
            'fire_time_type': fire_time_type,
            'special': special,
        })

    def clean_case_type(self):
        # todo check start_condition type when we get to the complex form
        case_property = self.cleaned_data['case_type'].strip()
        if not case_property:
            raise ValidationError("Please specify a case type.")
        return case_property

    def clean_start_property(self):
        if self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_PROPERTY:
            start_property = self.cleaned_data['start_property'].strip()
            if not start_property:
                raise ValidationError("Please enter a case property for the match criteria.")
            return start_property
        return None

    def clean_start_match_type(self):
        if self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_PROPERTY:
            return self.cleaned_data['start_match_type']
        return None

    def clean_start_value(self):
        if (self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_PROPERTY
           and self.cleaned_data['start_match_type'] != MATCH_ANY_VALUE):
            start_value = self.cleaned_data['start_value'].strip()
            if not start_value:
                raise ValidationError("You must specify a value for the case property match criteria.")
            return start_value
        return None

    def clean_start_property_offset(self):
        if self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_PROPERTY:
            if self.cleaned_data['start_property_offset_type'] == START_PROPERTY_OFFSET_IMMEDIATE:
                return 0
            start_property_offset = self.cleaned_data['start_property_offset']
            if start_property_offset < 0:
                raise ValidationError("Please enter a positive number.")
            return start_property_offset
        return None

    def clean_start_date(self):
        if self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_DATE:
            start_date = self.cleaned_data['start_date'].strip()
            if not start_date:
                raise ValidationError("You must specify a case property that will provide the start date.")
            return start_date
        return None

    def clean_start_date_offset(self):
        if self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_DATE:
            start_date_offset = self.cleaned_data['start_date_offset']
            if start_date_offset < 0:
                raise ValidationError("Please enter a positive number.")
            if self.cleaned_data['start_date_offset_type'] == START_DATE_OFFSET_BEFORE:
                return -start_date_offset
            return start_date_offset
        return None

    def clean_recipient_case_match_property(self):
        if self.cleaned_data['recipient'] == RECIPIENT_SUBCASE:
            case_property = self.cleaned_data['recipient_case_match_property'].strip()
            if not case_property:
                raise ValidationError("You must specify a case property for the case's child case.")
            return case_property
        return None

    def clean_recipient_case_match_type(self):
        if self.cleaned_data['recipient'] == RECIPIENT_SUBCASE:
            return self.cleaned_data['recipient_case_match_type']
        return None

    def clean_case_match_value(self):
        if (self.cleaned_data['recipient'] == RECIPIENT_SUBCASE
           and self.cleaned_data['recipient_case_match_type'] != MATCH_ANY_VALUE):
            match_value = self.cleaned_data['case_match_value'].strip()
            if not match_value:
                raise ValidationError("You must provide a value.")
            return match_value
        return None

    def clean_events(self):
        method = self.cleaned_data['method']
        try:
            events = json.loads(self.cleaned_data['events'])
        except ValueError:
            raise ValidationError("A valid JSON object was not passed in the events input.")

        for event in events:
            eventForm = CaseReminderEventForm(
                data=event,
            )
            if not eventForm.is_valid():
                raise ValidationError("Your event form didn't turn out quite right.")

            event.update(eventForm.cleaned_data)

            # the reason why we clean the following fields here instead of eventForm is so that
            # we can utilize the ValidationErrors for this field.

            # clean message:
            if method == METHOD_IVR_SURVEY or method == METHOD_SMS_SURVEY:
                event['message'] = {}
            else:
                translations = event.get('message', {})
                for lang, msg in translations.items():
                    if not msg:
                        del translations[lang]
                if not translations:
                    raise ValidationError("You must have at least one message filled in.")

            # clean form_unique_id:
            if method == METHOD_SMS or method == METHOD_SMS_CALLBACK:
                event['form_unique_id'] = None
            else:
                if not event.get('form_unique_id'):
                    raise ValidationError("Please create a form for the survey first, and then create "
                                          "the reminder.")

            fire_time_type = event['fire_time_type']

            # clean fire_time:
            if event['is_immediate'] or fire_time_type == FIRE_TIME_CASE_PROPERTY:
                event['fire_time'] = time()

            # clean fire_time_aux:
            if fire_time_type != FIRE_TIME_CASE_PROPERTY:
                event['fire_time_aux'] = None
            elif not event.get('fire_time_aux'):
                raise ValidationError("Please enter the case property from which to pull the time.")

            # clean time_window_length:
            time_window_length = event['time_window_length']
            if fire_time_type != FIRE_TIME_RANDOM:
                event['time_window_length'] = 0
            elif not (0 < time_window_length < 1440):
                raise ValidationError(_("Window Length must be greater than 0 and less than 1440 minutes."))

            # clean day_num:
            if self.ui_type == UI_SIMPLE_FIXED or event['is_immediate']:
                event['day_num'] = 0

            # clean callback_timeout_intervals:
            event["callback_timeout_intervals"] = []
            if method == METHOD_SMS_CALLBACK:
                timeouts_str = event["callback_timeout_intervals"].split(",")
                timeouts_int = []
                for t in timeouts_str:
                    try:
                        t = int(t)
                        assert t > 0
                        timeouts_int.append(t)
                    except (ValueError, AssertionError):
                        raise ValidationError("Timeout intervals must be a list of positive numbers "
                                              "separated by commas.")
                event["callback_timeout_intervals"] = timeouts_int

            # delete all data that was just UI based:
            del event['message_data']  # this is only for storing the stringified version of message
            del event['is_immediate']
        return events

    def clean_schedule_length(self):
        if self.cleaned_data['repeat_type'] == REPEAT_TYPE_NO:
            return 0
        value = self.cleaned_data['schedule_length']
        event_interpretation = self.cleaned_data["event_interpretation"]
        if event_interpretation == EVENT_AS_OFFSET and value < 0:
            raise ValidationError("Please enter a non-negative number.")
        elif event_interpretation == EVENT_AS_SCHEDULE and value <= 0:
            raise ValidationError("Please enter a positive number.")
        return value

    def clean_max_iteration_count(self):
        repeat_type = self.cleaned_data['repeat_type']
        if repeat_type == REPEAT_TYPE_NO:
            return 1
        if repeat_type == REPEAT_TYPE_INDEFINITE:
            return -1
        max_iteration_count = self.cleaned_data['max_iteration_count']
        if max_iteration_count < 0:
            raise ValidationError("Please enter a positive number.")
        if max_iteration_count == 0:
            raise ValidationError("Please enter a number that is 1 or greater.")
        return max_iteration_count

    def clean_until(self):
        if self.cleaned_data['stop_condition'] == STOP_CONDITION_CASE_PROPERTY:
            value = self.cleaned_data['until'].strip()
            if not value:
                raise ValidationError("You must specify a case property for the stop condition.")
            return value
        return None

    def clean_max_question_retries(self):
        value = self.cleaned_data['max_question_retries']
        try:
            value = int(value)
        except ValueError:
            raise ValidationError("Max question retries must be an integer.")
        return value

    def save(self, reminder_handler):
        if not isinstance(reminder_handler, CaseReminderHandler):
            raise ValueError("You must save to a CaseReminderHandler object!")

        events = self.cleaned_data['events']
        event_objects = []
        for event in events:
            new_event = CaseReminderEvent()
            for prop, val in event.items():
                setattr(new_event, prop, val)
            event_objects.append(new_event)
        reminder_handler.events = event_objects

        # set reminders created by this UI as inactive until we make sure it's bug free
        reminder_handler.active = False

        for field in [
            'nickname',
            'case_type',
            'start_property',
            'start_match_type',
            'start_value',
            'start_date',
            'recipient',
            'recipient_case_match_property',
            'recipient_case_match_type',
            'recipient_case_match_value',
            'method',
            'event_interpretation',
            'repeat_type',
            'schedule_length',
            'max_iteration_count',
            'stop_condition',
            'until',
            'submit_partial_forms',
            'include_case_side_effects',
            'default_lang',
            'max_question_retries',
        ]:
            setattr(reminder_handler, field, self.cleaned_data[field])

        start_property_offset = self.cleaned_data['start_property_offset']
        start_date_offset = self.cleaned_data['start_date_offset']
        reminder_handler.start_offset = (start_property_offset
                                         if start_property_offset is not None else start_date_offset)
        reminder_handler.ui_type = self.ui_type
        reminder_handler.domain = self.domain

        reminder_handler.save()

    @classmethod
    def compute_initial(cls, reminder_handler):
        initial = {}
        fields = cls.__dict__['base_fields'].keys()
        for field in fields:
            try:
                current_val = getattr(reminder_handler, field, Ellipsis)
                if field == 'events':
                    for event in current_val:
                        if not event.message:
                            event.message = {(reminder_handler.default_lang or 'en'): ''}
                        if event.form_unique_id:
                            form = CCHQForm.get_form(event.form_unique_id)
                            event.form_unique_id = json.dumps({
                                'text': form.full_path_name,
                                'id': event.form_unique_id,
                            })
                    current_val = json.dumps([e.to_json() for e in current_val])
                if field == 'callback_timeout_intervals':
                    current_val = ",".join(current_val)
                if current_val is not Ellipsis:
                    initial[field] = current_val
            except AttributeError:
                pass

        if reminder_handler.start_date is None:
            start_reminder_on = START_REMINDER_ON_CASE_PROPERTY
            initial['start_property_offset_type'] = (START_PROPERTY_OFFSET_IMMEDIATE
                                                     if reminder_handler.start_offset == 0
                                                     else START_PROPERTY_OFFSET_DELAY)
        else:
            start_reminder_on = START_REMINDER_ON_CASE_DATE
            initial['start_date_offset_type'] = (START_DATE_OFFSET_BEFORE if reminder_handler.start_offset <= 0
                                                 else START_DATE_OFFSET_AFTER)

        start_offset = abs(reminder_handler.start_offset or 0)

        if len(reminder_handler.events) > 0:
            initial['event_timing'] = cls._format_event_timing_choice(
                reminder_handler.event_interpretation,
                reminder_handler.events[0].fire_time_type,
                EVENT_TIMING_IMMEDIATE if reminder_handler.events[0].fire_time == time() else None,
            )

        initial.update({
            'start_reminder_on': start_reminder_on,
            'start_property_offset': start_offset,
            'start_date_offset': start_offset,
        })

        return initial


class CaseReminderEventForm(forms.Form):
    """
    This form creates or modifies a CaseReminderEvent.
    """
    fire_time_type = forms.ChoiceField(
        choices=(
            (FIRE_TIME_DEFAULT, "Default"),
            (FIRE_TIME_CASE_PROPERTY, "Case Property"),  # not valid when method != EVENT_AS_SCHEDULE
            (FIRE_TIME_RANDOM, "Random"),  # not valid when method != EVENT_AS_SCHEDULE
        ),
        widget=forms.HiddenInput,  # don't actually display this widget to the user for now, but validate as choice
    )

    # EVENT_AS_OFFSET: number of days after last fire
    # EVENT_AS_SCHEDULE: number of days since the current event cycle began
    day_num = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput,
    )

    # EVENT_AS_OFFSET: number of HH:MM:SS after last fire
    # EVENT_AS_SCHEDULE: time of day
    fire_time = forms.TimeField(
        required=False,
        label="HH:MM:SS",
    )

    # method must be EVENT_AS_SCHEDULE
    fire_time_aux = forms.CharField(
        required=False,
        label="Enter a Case Property",
    )

    time_window_length = forms.IntegerField(
        label="Window Length (minutes)",
        required=False
    )

    # messages is visible when the method of the reminder is METHOD_SMS or METHOD_SMS_CALLBACK
    # value will be a dict of {language: message}
    message_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    # callback_timeout_intervals is visible when method of reminder is METHOD_SMS_CALLBACK
    # a list of comma separated integers
    callback_timeout_intervals = forms.CharField(
        required=False,
        label="Timeouts",
    )

    # form_unique_id is visible when the method of the reminder is SMS_SURVEY or IVR_SURVEY
    form_unique_id = forms.CharField(
        required=False,
        label="Survey",
    )

    def __init__(self, ui_type=None, *args, **kwargs):
        super(CaseReminderEventForm, self).__init__(*args, **kwargs)

        self.ui_type = ui_type

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Field('message_data', data_bind="value: message_data, attr: {id: ''}"),
            crispy.Div(data_bind="template: {name: 'event-message-template', foreach: messageTranslations}, "
                                 "visible: isMessageVisible"),
            crispy.Div(
                crispy.Field(
                    'form_unique_id',
                    data_bind="value: form_unique_id, attr: {id: ''}",
                    css_class="input-xxlarge",
                ),
                data_bind="visible: isSurveyVisible",
            ),
        )

        self.helper_fire_time = FormHelper()
        self.helper_fire_time.form_tag = False
        self.helper_fire_time.layout = crispy.Layout(
            crispy.Div(
                crispy.HTML('<input type="text" data-bind="value: fire_time" '
                            'data-timeset="true" class="input-small" />'),
                crispy.HTML('<span class="add-on"><i class="icon-time"></i>'),
                css_class="input-append bootstrap-timepicker",
                style="margin-left:5px;",
                data_bind="visible: isFireTimeVisible",
            ),
            crispy.Div(
                InlineField(
                    'fire_time_aux',
                    data_bind="value: fire_time_aux, attr: {id: ''}",
                    css_class="input-large",
                ),
                css_class="help-inline",
                data_bind="visible: isFireTimeAuxVisible",
                style="margin-left: 5px;",
            ),
        )

        self.helper_general = FormHelper()
        self.helper_general.form_tag = False
        self.helper_general.layout = crispy.Layout(
            crispy.Div(
                crispy.Field('time_window_length', data_bind="value: time_window_length, attr: {id: ''}"),
                data_bind="visible: isWindowLengthVisible",
            ),
            crispy.Field('fire_time_type', data_bind="value: fire_time_type, attr: {id: ''}"),
            crispy.Field('day_num', data_bind="value: day_num, attr: {id: ''}"),
        )

        self.helper_timeouts = FormHelper()
        self.helper_timeouts.form_tag = False
        self.helper_timeouts.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'callback_timeout_intervals',
                    data_bind="value: callback_timeout_intervals, attr: {id: ''}",
                    placeholder="e.g. 30,60,180",
                ),
                data_bind="visible: isCallbackTimeoutsVisible",
            ),
        )


class CaseReminderEventMessageForm(forms.Form):
    """
    This form specifies the UI for messages in CaseReminderEventForm.
    """
    language = forms.CharField(
        required=False,
        widget=forms.HiddenInput
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea
    )

    def __init__(self, *args, **kwargs):
        super(CaseReminderEventMessageForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Field('language', data_bind="value: language"),
            BootstrapMultiField(
                'Message <span data-bind="text:languageLabel"></span>',
                InlineField(
                    'message',
                    data_bind="value: message, valueUpdate: 'keyup'",
                    css_class="input-xlarge",
                    rows="2",
                ),
                crispy.Div(
                    style="padding-top: 10px",
                    data_bind="template: { name: 'event-message-length-template' }"
                )
            ),
        )


def clean_selection(value):
    if value == "" or value is None:
        raise ValidationError(_("Please make a selection."))
    else:
        return value

class OneTimeReminderForm(Form):
    _cchq_domain = None
    send_type = ChoiceField(choices=NOW_OR_LATER)
    date = CharField(required=False)
    time = CharField(required=False)
    datetime = DateTimeField(required=False)
    recipient_type = ChoiceField(choices=ONE_TIME_RECIPIENT_CHOICES)
    case_group_id = CharField(required=False)
    user_group_id = CharField(required=False)
    content_type = ChoiceField(choices=CONTENT_CHOICES)
    message = TrimmedCharField(required=False)
    form_unique_id = CharField(required=False)

    def clean_recipient_type(self):
        return clean_selection(self.cleaned_data.get("recipient_type"))

    def clean_case_group_id(self):
        if self.cleaned_data.get("recipient_type") == RECIPIENT_SURVEY_SAMPLE:
            value = clean_selection(self.cleaned_data.get("case_group_id"))
            try:
                group = CommCareCaseGroup.get(value)
                assert group.doc_type == "CommCareCaseGroup"
                assert group.domain == self._cchq_domain
            except Exception:
                raise ValidationError(_("Invalid selection."))
            return value
        else:
            return None

    def clean_user_group_id(self):
        if self.cleaned_data.get("recipient_type") == RECIPIENT_USER_GROUP:
            value = clean_selection(self.cleaned_data.get("user_group_id"))
            try:
                group = Group.get(value)
                assert group.doc_type == "Group"
                assert group.domain == self._cchq_domain
            except Exception:
                raise ValidationError(_("Invalid selection."))
            return value
        else:
            return None

    def clean_date(self):
        if self.cleaned_data.get("send_type") == SEND_NOW:
            return None
        else:
            value = self.cleaned_data.get("date")
            validate_date(value)
            return parse(value).date()

    def clean_time(self):
        if self.cleaned_data.get("send_type") == SEND_NOW:
            return None
        else:
            value = self.cleaned_data.get("time")
            validate_time(value)
            return parse(value).time()

    def clean_message(self):
        value = self.cleaned_data.get("message")
        if self.cleaned_data.get("content_type") == METHOD_SMS:
            if value:
                return value
            else:
                raise ValidationError("This field is required.")
        else:
            return None

    def clean_datetime(self):
        utcnow = datetime.utcnow()
        timezone = report_utils.get_timezone(None, self._cchq_domain) # Use project timezone only
        if self.cleaned_data.get("send_type") == SEND_NOW:
            start_datetime = utcnow + timedelta(minutes=1)
        else:
            dt = self.cleaned_data.get("date")
            tm = self.cleaned_data.get("time")
            if dt is None or tm is None:
                return None
            start_datetime = datetime.combine(dt, tm)
            start_datetime = tz_utils.adjust_datetime_to_timezone(start_datetime, timezone.zone, pytz.utc.zone)
            start_datetime = start_datetime.replace(tzinfo=None)
            if start_datetime < utcnow:
                raise ValidationError(_("Date and time cannot occur in the past."))
        return start_datetime

    def clean_form_unique_id(self):
        if self.cleaned_data.get("content_type") == METHOD_SMS_SURVEY:
            value = self.cleaned_data.get("form_unique_id")
            if value is None:
                raise ValidationError(_("Please create a form first, and then create the broadcast."))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

class RecordListWidget(Widget):
    
    # When initialized, expects to be passed attrs={"input_name" : < first dot-separated name of all related records in the html form >}
    
    def value_from_datadict(self, data, files, name, *args, **kwargs):
        input_name = self.attrs["input_name"]
        raw = {}
        for key in data:
            if key.startswith(input_name + "."):
                raw[key] = data[key]
        
        data_dict = DotExpandedDict(raw)
        data_list = []
        if len(data_dict) > 0:
            for key in sorted(data_dict[input_name].iterkeys()):
                data_list.append(data_dict[input_name][key])
        
        return data_list

class RecordListField(Field):
    required = None
    label = None
    initial = None
    widget = None
    help_text = None
    
    # When initialized, expects to be passed kwarg input_name, which is the first dot-separated name of all related records in the html form
    
    def __init__(self, required=True, label="", initial=[], widget=None, help_text="", *args, **kwargs):
        self.required = required
        self.label = label
        self.initial = initial
        self.widget = RecordListWidget(attrs={"input_name" : kwargs["input_name"]})
        self.help_text = help_text
    
    def clean(self, value):
        return value

class SurveyForm(Form):
    name = CharField()
    waves = RecordListField(input_name="wave")
    followups = RecordListField(input_name="followup")
    samples = RecordListField(input_name="sample")
    send_automatically = BooleanField(required=False)
    send_followup = BooleanField(required=False)
    
    def clean_waves(self):
        value = self.cleaned_data["waves"]
        datetimes = {}
        samples = [CommCareCaseGroup.get(sample["sample_id"]) for sample in self.cleaned_data.get("samples",[])]
        utcnow = datetime.utcnow()
        followups = [int(followup["interval"]) for followup in self.cleaned_data.get("followups", [])]
        followup_duration = sum(followups)
        start_end_intervals = []
        for wave_json in value:
            validate_date(wave_json["date"])
            validate_date(wave_json["end_date"])
            validate_time(wave_json["time"])
            
            # Convert the datetime to a string and compare it against the other datetimes
            # to make sure no two waves have the same start timestamp
            date = parse(wave_json["date"]).date()
            time = parse(wave_json["time"]).time()
            d8time = datetime.combine(date, time)
            datetime_string = string_to_datetime(d8time)
            if datetimes.get(datetime_string, False):
                raise ValidationError("Two waves cannot be scheduled at the same date and time.")
            datetimes[datetime_string] = True
            
            # Validate end date
            end_date = parse(wave_json["end_date"]).date()
            end_datetime = datetime.combine(end_date, time)
            days_between = (end_date - date).days
            if days_between < 1:
                raise ValidationError("End date must come after start date.")
            if days_between <= followup_duration:
                raise ValidationError("End date must come after all followups.")
            
            start_end_intervals.append((d8time, end_datetime))
            
            if wave_json["form_id"] == "--choose--":
                raise ValidationError("Please choose a questionnaire.")
            
            # If the wave was editable, make sure it is not being scheduled in the past for any sample
            if "ignore" not in wave_json:
                for sample in samples:
                    if CaseReminderHandler.timestamp_to_utc(sample, d8time) < utcnow:
                        raise ValidationError("Waves cannot be scheduled in the past.")
        
        # Ensure wave start and end dates do not overlap
        start_end_intervals.sort(key = lambda t : t[0])
        i = 0
        last_end = None
        for start_end in start_end_intervals:
            if i > 0 and (start_end[0] - last_end).days < 1:
                raise ValidationError("Waves must be scheduled at least one day apart.")
            i += 1
            last_end = start_end[1]
        
        return value
    
    def clean_followups(self):
        send_followup = self.cleaned_data["send_followup"]
        if send_followup:
            value = self.cleaned_data["followups"]
            for followup in value:
                try:
                    interval = int(followup["interval"])
                    assert interval > 0
                except (ValueError, AssertionError):
                    raise ValidationError("Follow-up intervals must be positive integers.")
                
            return value
        else:
            return []
    
    def clean_samples(self):
        value = self.cleaned_data["samples"]
        for sample_json in value:
            if sample_json["sample_id"] == "--choose--":
                raise ValidationError("Please choose a sample.")
            if sample_json.get("cati_operator", None) is None and sample_json["method"] == "CATI":
                raise ValidationError("Please create a mobile worker to use as a CATI Operator.")
        return value

    def clean(self):
        cleaned_data = super(SurveyForm, self).clean()
        return cleaned_data


class SurveySampleForm(Form):
    name = CharField()
    sample_contacts = RecordListField(input_name="sample_contact")
    time_zone = TimeZoneChoiceField()
    use_contact_upload_file = ChoiceField(choices=YES_OR_NO)
    contact_upload_file = FileField(required=False)
    
    def clean_sample_contacts(self):
        value = self.cleaned_data["sample_contacts"]
        if self.cleaned_data.get("use_contact_upload_file", "N") == "N":
            if len(value) == 0:
                raise ValidationError("Please add at least one contact.")
            for contact in value:
                contact["phone_number"] = validate_phone_number(contact["phone_number"])
        return value
    
    def clean_contact_upload_file(self):
        value = self.cleaned_data.get("contact_upload_file", None)
        if self.cleaned_data.get("use_contact_upload_file", "N") == "Y":
            if value is None:
                raise ValidationError("Please choose a file.")
            
            try:
                workbook = WorkbookJSONReader(value)
            except InvalidFileException:
                raise ValidationError("Invalid format. Please convert to Excel 2007 or higher (.xlsx) and try again.")
            
            try:
                worksheet = workbook.get_worksheet()
            except WorksheetNotFound:
                raise ValidationError("Workbook has no worksheets.")
            
            contacts = []
            for row in worksheet:
                if "PhoneNumber" not in row:
                    raise ValidationError("Column 'PhoneNumber' not found.")
                contacts.append({"phone_number" : validate_phone_number(row.get("PhoneNumber"))})
            
            if len(contacts) == 0:
                raise ValidationError(_("Please add at least one contact."))
            
            return contacts
        else:
            return None

class EditContactForm(Form):
    phone_number = CharField()
    
    def clean_phone_number(self):
        value = self.cleaned_data.get("phone_number")
        return validate_phone_number(value)

class ListField(Field):
    
    def __init__(self, *args, **kwargs):
        kwargs["widget"] = CheckboxSelectMultiple
        super(ListField, self).__init__(*args, **kwargs)
    
    def clean(self, value):
        return value

class RemindersInErrorForm(Form):
    selected_reminders = ListField(required=False)

class KeywordForm(Form):
    _cchq_domain = None
    _sk_id = None
    keyword = CharField()
    form_unique_id = CharField(required=False)
    form_type = ChoiceField(choices=FORM_TYPE_CHOICES)
    use_custom_delimiter = BooleanField(required=False)
    delimiter = CharField(required=False)
    use_named_args = BooleanField(required=False)
    use_named_args_separator = BooleanField(required=False)
    named_args = RecordListField(input_name="named_args")
    named_args_separator = CharField(required=False)
    
    def clean_keyword(self):
        value = self.cleaned_data.get("keyword")
        if value is not None:
            value = value.strip().upper()
        if value is None or value == "":
            raise ValidationError(_("This field is required."))
        if len(value.split()) > 1:
            raise ValidationError(_("Keyword should be one word."))
        duplicate = SurveyKeyword.get_keyword(self._cchq_domain, value)
        if duplicate is not None and duplicate._id != self._sk_id:
            raise ValidationError(_("Keyword already exists."))
        return value
    
    def clean_form_unique_id(self):
        value = self.cleaned_data.get("form_unique_id")
        if value is None:
            raise ValidationError(_("Please create a form first, and then add a keyword for it."))
        validate_form_unique_id(value, self._cchq_domain)
        return value
    
    def clean_delimiter(self):
        value = self.cleaned_data.get("delimiter", None)
        if self.cleaned_data.get("form_type") == FORM_TYPE_ALL_AT_ONCE and self.cleaned_data.get("use_custom_delimiter", False):
            if value is not None:
                value = value.strip()
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None
    
    def clean_named_args(self):
        if self.cleaned_data.get("form_type") == FORM_TYPE_ALL_AT_ONCE and self.cleaned_data.get("use_named_args", False):
            use_named_args_separator = self.cleaned_data.get("use_named_args_separator", False)
            value = self.cleaned_data.get("named_args")
            data_dict = {}
            for d in value:
                name = d["name"].strip().upper()
                xpath = d["xpath"].strip()
                if name == "" or xpath == "":
                    raise ValidationError(_("Name and xpath are both required fields."))
                for k, v in data_dict.items():
                    if not use_named_args_separator and (k.startswith(name) or name.startswith(k)):
                        raise ValidationError(_("Cannot have two names overlap: ") + "(%s, %s)" % (k, name))
                    if use_named_args_separator and k == name:
                        raise ValidationError(_("Cannot use the same name twice: ") + name)
                    if v == xpath:
                        raise ValidationError(_("Cannot reference the same xpath twice: ") + xpath)
                data_dict[name] = xpath
            return data_dict
        else:
            return {}
    
    def clean_named_args_separator(self):
        value = self.cleaned_data.get("named_args_separator", None)
        if self.cleaned_data.get("form_type") == FORM_TYPE_ALL_AT_ONCE and self.cleaned_data.get("use_named_args", False) and self.cleaned_data.get("use_named_args_separator", False):
            if value is not None:
                value = value.strip()
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            if value == self.cleaned_data.get("delimiter"):
                raise ValidationError(_("Delimiter and joining character cannot be the same."))
            return value
        else:
            return None

