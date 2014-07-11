import copy
import json
import re
from couchdbkit import ResourceNotFound
from crispy_forms.bootstrap import InlineField, FormActions, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
import pytz
from datetime import timedelta, datetime, time
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.fields import *
from django.forms.forms import Form
from django.forms.widgets import CheckboxSelectMultiple
from django import forms
from django.forms import Field, Widget
from corehq.apps.reminders.util import DotExpandedDict, get_form_list
from casexml.apps.case.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.crispy import (
    BootstrapMultiField, FieldsetAccordionGroup, HiddenFieldWithErrors,
    FieldWithHelpBubble, InlineColumnField, ErrorsOnlyField,
)
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
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
    RECIPIENT_ALL_SUBCASES,
)
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from dateutil.parser import parse
from dimagi.utils.excel import WorkbookJSONReader, WorksheetNotFound
from openpyxl.shared.exc import InvalidFileException
from django.utils.translation import ugettext as _, ugettext_noop
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

KEYWORD_CONTENT_CHOICES = (
    (METHOD_SMS, _("SMS Message")),
    (METHOD_SMS_SURVEY, _("SMS Interactive Survey")),
)

KEYWORD_RECIPIENT_CHOICES = (
    (RECIPIENT_USER_GROUP, _("User Group")),
    (RECIPIENT_OWNER, _("The case's owner")),
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
    (RECIPIENT_USER_GROUP, _("User Group")),
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
    if not isinstance(value, basestring) or time_regex.match(value) is None:
        raise ValidationError("Times must be in hh:mm format.")
    return parse(value).time()

def validate_form_unique_id(form_unique_id, domain):
    try:
        form = CCHQForm.get_form(form_unique_id)
        app = form.get_app()
        assert app.domain == domain
    except Exception:
        raise ValidationError(_("Invalid form chosen."))

def clean_group_id(group_id, expected_domain):
    try:
        assert group_id is not None
        assert group_id != ""
        group = Group.get(group_id)
        assert group.doc_type == "Group"
        assert group.domain == expected_domain
        return group_id
    except Exception:
        raise ValidationError(_("Invalid selection."))

def clean_case_group_id(group_id, expected_domain):
    try:
        assert group_id is not None
        assert group_id != ""
        group = CommCareCaseGroup.get(group_id)
        assert group.doc_type == "CommCareCaseGroup"
        assert group.domain == expected_domain
        return group_id
    except Exception:
        raise ValidationError(_("Invalid selection."))

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
    validators = None
    
    def __init__(self, required=True, label="", initial=None, widget=None, help_text="", *args, **kwargs):
        self.required = required
        self.label = label
        self.initial = initial or []
        self.widget = widget or EventWidget()
        self.help_text = help_text
        self.validators = []
    
    def clean(self, value):
        # See clean_events() method in the form for validation
        return value

class ComplexCaseReminderForm(Form):
    """
    A form used to create/edit CaseReminderHandlers with any type of schedule.
    """
    _cchq_is_superuser = False
    _cchq_use_custom_content_handler = False
    _cchq_custom_content_handler = None
    _cchq_domain = None
    use_custom_content_handler = BooleanField(required=False)
    custom_content_handler = TrimmedCharField(required=False)
    active = BooleanField(required=False)
    nickname = CharField(error_messages={"required":"Please enter the name of this reminder definition."})
    start_condition_type = CharField()
    case_type = CharField(required=False)
    method = ChoiceField(choices=(('sms', 'SMS'),))
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
    user_group_id = CharField(required=False)

    def __init__(self, *args, **kwargs):
        can_use_survey = kwargs.pop('can_use_survey', False)
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

        if can_use_survey:
            self.fields['method'].choices = METHOD_CHOICES
        
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

    def clean_use_custom_content_handler(self):
        if self._cchq_is_superuser:
            return self.cleaned_data.get("use_custom_content_handler")
        else:
            return self._cchq_use_custom_content_handler

    def clean_custom_content_handler(self):
        if self._cchq_is_superuser:
            value = self.cleaned_data.get("custom_content_handler")
            if self.cleaned_data.get("use_custom_content_handler"):
                if value in settings.ALLOWED_CUSTOM_CONTENT_HANDLERS:
                    return value
                else:
                    raise ValidationError(_("Invalid custom content handler."))
            else:
                return None
        else:
            return self._cchq_custom_content_handler

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
            return clean_case_group_id(value, self._cchq_domain)
        else:
            return None

    def clean_user_group_id(self):
        if self.cleaned_data.get("recipient") == RECIPIENT_USER_GROUP:
            value = self.cleaned_data.get("user_group_id")
            return clean_group_id(value, self._cchq_domain)
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
            if (method in [METHOD_SMS, METHOD_SMS_CALLBACK]) and (not self.cleaned_data.get("use_custom_content_handler")):
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
            if (method in [METHOD_SMS, METHOD_SMS_CALLBACK]) and (not self.cleaned_data.get("use_custom_content_handler")):
                for e in events:
                    if default_lang not in e.message:
                        self._errors["events"] = self.error_class(["Every message must contain a translation for the default language."])
                        del cleaned_data["events"]
                        break
        
        return cleaned_data


MATCH_TYPE_CHOICES = (
    (MATCH_ANY_VALUE, ugettext_noop("exists.")),
    (MATCH_EXACT, ugettext_noop("equals")),
    (MATCH_REGEX, ugettext_noop("matches regular expression")),
)

START_REMINDER_ALL_CASES = 'start_all_cases'
START_REMINDER_ON_CASE_DATE = 'case_date'
START_REMINDER_ON_CASE_PROPERTY = 'case_property'

START_DATE_OFFSET_BEFORE = 'offset_before'
START_DATE_OFFSET_AFTER = 'offset_after'

START_PROPERTY_OFFSET_DELAY = 'offset_delay'
START_PROPERTY_OFFSET_IMMEDIATE = 'offset_immediate'

START_PROPERTY_ALL_CASES_VALUE = '_id'

EVENT_TIMING_IMMEDIATE = 'immediate'

REPEAT_TYPE_NO = 'no_repeat'
REPEAT_TYPE_INDEFINITE = 'indefinite'
REPEAT_TYPE_SPECIFIC = 'specific'

STOP_CONDITION_CASE_PROPERTY = 'case_property'


class BaseScheduleCaseReminderForm(forms.Form):
    """
    This form creates a new CaseReminder. It is the most basic version, no advanced options (like language).
    """
    nickname = forms.CharField(
        label=ugettext_noop("Name"),
        error_messages={
            'required': ugettext_noop("Please enter a name for this reminder."),
        }
    )

    # Fieldset: Send Options
    # simple has start_condition_type = CASE_CRITERIA by default
    case_type = forms.CharField(
        required=False,
        label=ugettext_noop("Send For Case Type"),
    )
    start_reminder_on = forms.ChoiceField(
        label=ugettext_noop("Send Reminder To"),
        required=False,
        choices=(
            (START_REMINDER_ALL_CASES, ugettext_noop("All Cases")),
            (START_REMINDER_ON_CASE_PROPERTY, ugettext_noop("Only Cases in Following State")),
            (START_REMINDER_ON_CASE_DATE, ugettext_noop("Cases Based on Date in Case")),
        ),
    )
    ## send options > start_reminder_on = case_date
    start_property = forms.CharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )
    start_match_type = forms.ChoiceField(
        required=False,
        choices=MATCH_TYPE_CHOICES,
    )
    # only shows up if start_match_type != MATCH_ANY_VALUE
    start_value = forms.CharField(
        required=False,
        label=ugettext_noop("Value")
    )
    # this is a UI control that determines how start_offset is calculated (0 or an integer)
    start_property_offset_type = forms.ChoiceField(
        required=False,
        choices=(
            (START_PROPERTY_OFFSET_IMMEDIATE, ugettext_noop("Immediately")),
            (START_PROPERTY_OFFSET_DELAY, ugettext_noop("Delay By")),
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
        label=ugettext_noop("Case Property"),
    )
    start_date_offset_type = forms.ChoiceField(
        required=False,
        choices=(
            (START_DATE_OFFSET_BEFORE, ugettext_noop("Before Date By")),
            (START_DATE_OFFSET_AFTER, ugettext_noop("After Date By")),
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
            (RECIPIENT_CASE, ugettext_noop("Case")),
            (RECIPIENT_OWNER, ugettext_noop("Case Owner")),
            (RECIPIENT_USER, ugettext_noop("Last User Who Modified Case")),
            (RECIPIENT_USER_GROUP, ugettext_noop("Mobile Worker Group")),
            (RECIPIENT_ALL_SUBCASES, ugettext_noop("All Child Cases")),
            (RECIPIENT_SUBCASE, ugettext_noop("Specific Child Case")),
            (RECIPIENT_PARENT_CASE, ugettext_noop("Parent Case")),
        ),
    )
    ## recipient = RECIPIENT_SUBCASE
    recipient_case_match_property = forms.CharField(
        label=ugettext_noop("Case Property"),
        required=False
    )
    recipient_case_match_type = forms.ChoiceField(
        required=False,
        choices=MATCH_TYPE_CHOICES,
    )
    recipient_case_match_value = forms.CharField(
        label=ugettext_noop("Value"),
        required=False
    )
    ## recipient = RECIPIENT_USER_GROUP
    user_group_id = ChoiceField(
        required=False,
        label=ugettext_noop("Mobile Worker Group"),
    )

    # Fieldset: Message Content
    method = forms.ChoiceField(
        label=ugettext_noop("Send"),
        choices=(
            (METHOD_SMS, ugettext_noop("SMS")),
        ),
    )

    global_timeouts = forms.CharField(
        label=ugettext_noop("Timeouts"),
        required=False,
    )

    # contains a string-ified JSON object of events
    events = forms.CharField(
        required=False,
        widget=forms.HiddenInput
    )

    event_timing = forms.ChoiceField(
        label=ugettext_noop("Time of Day"),
    )

    event_interpretation = forms.ChoiceField(
        label=ugettext_noop("Schedule Type"),
        initial=EVENT_AS_OFFSET,
        choices=(
            (EVENT_AS_OFFSET, ugettext_noop("Offset-based")),
            (EVENT_AS_SCHEDULE, ugettext_noop("Schedule-based")),
        ),
        widget=forms.HiddenInput  # validate as choice, but don't show the widget.
    )

    # Fieldset: Repeat
    repeat_type = forms.ChoiceField(
        required=False,
        label=ugettext_noop("Repeat Reminder"),
        initial=REPEAT_TYPE_NO,
        choices=(
            (REPEAT_TYPE_NO, ugettext_noop("No")),  # reminder_type = ONE_TIME
            (REPEAT_TYPE_INDEFINITE, ugettext_noop("Indefinitely")),  # reminder_type = DEFAULT, max_iteration_count = -1
            (REPEAT_TYPE_SPECIFIC, ugettext_noop("Specific Number of Times")),
        )
    )
    # shown if repeat_type != 'no_repeat'
    schedule_length = forms.IntegerField(
        required=False,
        label=ugettext_noop("Repeat Every"),
    )
    # shown if repeat_type == 'specific' (0 if no_repeat, -1 if indefinite)
    max_iteration_count = forms.IntegerField(
        required=False,
        label=ugettext_noop("Number of Times"),
    )
    # shown if repeat_type != 'no_repeat'
    stop_condition = forms.ChoiceField(
        required=False,
        label="",
        choices=(
            ('', ugettext_noop('(none)')),
            (STOP_CONDITION_CASE_PROPERTY, ugettext_noop('Based on Case Property')),
        )
    )
    until = forms.CharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )

    # Advanced Toggle
    submit_partial_forms = forms.BooleanField(
        required=False,
        label=ugettext_noop("Submit Partial Forms"),
    )
    include_case_side_effects = forms.BooleanField(
        required=False,
        label=ugettext_noop("Include Case Changes for Partial Forms"),
    )
    default_lang = forms.ChoiceField(
        required=False,
        label=ugettext_noop("Default Language"),
        choices=(
            ('en', ugettext_noop("English (en)")),
        )
    )
    # only show if SMS_SURVEY or IVR_SURVEY is chosen
    max_question_retries = forms.ChoiceField(
        required=False,
        choices=((n, n) for n in QUESTION_RETRY_CHOICES)
    )

    force_surveys_to_use_triggered_case = forms.BooleanField(
        required=False,
        label=ugettext_noop("For Surveys, force answers to affect "
                              "case sending the survey."),
    )

    use_custom_content_handler = BooleanField(
        required=False,
        label=ugettext_noop("Use Custom Content Handler")
    )
    custom_content_handler = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Custom Content Handler")
    )

    def __init__(self, data=None, is_previewer=False,
                 domain=None, is_edit=False, can_use_survey=False,
                 use_custom_content_handler=False,
                 custom_content_handler=None,
                 available_languages=None, *args, **kwargs
    ):
        available_languages = available_languages or ['en']
        self.initial_event = {
            'day_num': 1,
            'fire_time_type': FIRE_TIME_DEFAULT,
            'message': dict([(l, '') for l in available_languages]),
        }

        if 'initial' not in kwargs:
            kwargs['initial'] = {
                'event_timing': self._format_event_timing_choice(EVENT_AS_OFFSET,
                                                                 FIRE_TIME_DEFAULT, EVENT_TIMING_IMMEDIATE),
                'events': json.dumps([self.initial_event])
            }

        super(BaseScheduleCaseReminderForm, self).__init__(data, *args, **kwargs)

        self.domain = domain
        self.is_edit = is_edit
        self.is_previewer = is_previewer
        self.use_custom_content_handler = use_custom_content_handler
        self.custom_content_handler = custom_content_handler

        self.fields['user_group_id'].choices = Group.choices_by_domain(self.domain)
        self.fields['default_lang'].choices = [(l, l) for l in available_languages]

        if can_use_survey:
            method_choices = copy.copy(self.fields['method'].choices)
            method_choices.append((METHOD_SMS_SURVEY, "SMS Survey"))
            self.fields['method'].choices = method_choices

        if is_previewer and can_use_survey:
            method_choices = copy.copy(self.fields['method'].choices)
            method_choices.extend([
                (METHOD_IVR_SURVEY, _("IVR Survey")),
                (METHOD_SMS_CALLBACK, _("SMS Expecting Callback")),
            ])
            self.fields['method'].choices = method_choices

        from corehq.apps.reminders.views import RemindersListView
        self.helper = FormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                crispy.Field(
                    'nickname',
                    css_class='input-large',
                ),
            ),
            self.section_start,
            self.section_recipient,
            self.section_message,
            self.section_repeat,
            self.section_advanced,
            FormActions(
                StrictButton(
                    _("Update Reminder") if is_edit else _("Create Reminder"),
                    css_class='btn-primary',
                    type='submit',
                ),
                crispy.HTML('<a href="%s" class="btn">%s</a>' % (
                    reverse(RemindersListView.urlname, args=[self.domain]),
                    _("Cancel")
                )),
            )
        )

    @property
    def ui_type(self):
        raise NotImplementedError("You must specify a ui_type for the reminder")

    @property
    def section_start(self):
        return crispy.Fieldset(
            _('Start'),
            crispy.HTML(
                '<p style="padding: 0; margin-bottom: 1.5em;">'
                '<i class="icon-info-sign"></i> %s</p>' % _(
                    "Choose what will cause this reminder to be sent"
                ),
            ),
            *self.section_start_fields
        )

    @property
    def section_start_fields(self):
        return [
            FieldWithHelpBubble(
                'case_type',
                css_class="input-xlarge",
                data_bind="value: case_type",
                data_placeholder=_("Enter a Case Type"),
                help_bubble_text=_(
                    "Choose which case type this reminder will be "
                    "sent out for."
                ),
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
                    _("When Case Property"),
                    InlineField(
                        'start_property',
                        css_class="input-xlarge",
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
                    _("Begin Sending"),
                    InlineField(
                        'start_property_offset_type',
                        data_bind="value: start_property_offset_type",
                        css_class="input-xlarge",
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
                    css_class="input-xlarge",
                ),
                BootstrapMultiField(
                    "",
                    InlineField(
                        'start_date_offset_type',
                        css_class="input-xlarge",
                    ),
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
        ]

    @property
    def section_recipient(self):
        return crispy.Fieldset(
            _("Recipient"),
            FieldWithHelpBubble(
                'recipient',
                data_bind="value: recipient",
                help_bubble_text=("The contact related to the case that reminder should go to.  The Case "
                                  "Owners are any mobile workers for which the case appears on their phone. "
                                  "For cases with child or parent cases, you can also send the message to those "
                                  "contacts. "),
                css_class="input-xlarge",
            ),
            BootstrapMultiField(
                _("When Case Property"),
                InlineField(
                    'recipient_case_match_property',
                    placeholder="Enter a Case Property",
                    css_class="input-xlarge",
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
            crispy.Div(
                crispy.Field(
                    'user_group_id',
                    css_class="input-xlarge",
                ),
                data_bind="visible: isRecipientGroup"
            ),
        )

    @property
    def section_message(self):
        return crispy.Fieldset(
            _("Message Content") if self.ui_type == UI_SIMPLE_FIXED else _("Schedule"),
            *self.section_message_fields
        )

    @property
    def section_message_fields(self):
        return [
            FieldWithHelpBubble(
                'method',
                data_bind="value: method",
                help_bubble_text=("Send a single SMS message or an interactive SMS survey. "
                                  "SMS surveys are designed in the Surveys or Application "
                                  "section. "),
                css_class="input-xlarge",
            ),
            crispy.Field('event_interpretation', data_bind="value: event_interpretation"),
            HiddenFieldWithErrors('events', data_bind="value: events"),
        ]

    @property
    def timing_fields(self):
        return [
            BootstrapMultiField(
                _("Time of Day"),
                InlineField(
                    'event_timing',
                    data_bind="value: event_timing",
                    css_class="input-xlarge",
                ),
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
            )
        ]

    @property
    def section_repeat(self):
        return crispy.Fieldset(
            _("Repeat"),
            crispy.Field(
                'repeat_type',
                data_bind="value: repeat_type",
                css_class="input-xlarge",
            ),
            crispy.Div(
                crispy.Field(
                    'max_iteration_count',
                    css_class="input-medium",
                ),
                data_bind="visible: isMaxIterationCountVisible",
            ),
            BootstrapMultiField(
                _("Repeat Every"),
                InlineField(
                    'schedule_length',
                    css_class="input-medium",
                ),
                crispy.HTML('<p class="help-inline">day(s)</p>'),
                data_bind="visible: isScheduleLengthVisible",
            ),
        )

    @property
    def section_advanced(self):
        return FieldsetAccordionGroup(
            _("Advanced Options"),
            BootstrapMultiField(
                _("Stop Condition"),
                InlineField(
                    'stop_condition',
                    data_bind="value: stop_condition",
                    css_class="input-xlarge",
                ),
                crispy.Div(
                    InlineField(
                        'until',
                        css_class="input-large",
                    ),
                    css_class="help-inline",
                    data_bind="visible: isUntilVisible",
                ),
                help_bubble_text=_("Reminders can be stopped after a date set in the case, or if a particular "
                                   "case property is set to OK.  Choose either a case property that is a date or "
                                   "a case property that is going to be set to Ok.  Reminders will always stop if "
                                   "the start condition is no longer true."),
                css_id="stop-condition-group",
            ),
            crispy.Div(
                BootstrapMultiField(
                    _("Default Language"),
                    InlineField(
                        'default_lang',
                        data_bind="options: available_languages, "
                                  "value: default_lang, "
                                  "optionsText: 'name', optionsValue: 'langcode'",
                        css_class="input-xlarge",
                    ),
                ),
                data_bind="visible: showDefaultLanguageOption",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'global_timeouts',
                    data_bind="value: global_timeouts",
                    placeholder="e.g. 30,60,180",
                    help_bubble_text=_(
                        "Will repeat the last message or question if the "
                        "user does not respond.  Specify each interval "
                        "(in minutes) separated by a comma. "
                        "After the last interval, the survey will be closed. "
                    ),
                ),
                data_bind="visible: isGlobalTimeoutsVisible",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'max_question_retries',
                    help_bubble_text=_("For IVR surveys, the number of times a person can provide an invalid "
                                       "answer before the call will hang up. ")
                ),
                data_bind="visible: isMaxQuestionRetriesVisible",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'submit_partial_forms',
                    data_bind="checked: submit_partial_forms",
                    help_bubble_text=_(
                        "For surveys, this will let forms be saved even if "
                        "the survey has not been completed and the user is "
                        "not responding."
                    ),
                ),
                data_bind="visible: isPartialSubmissionsVisible",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    'include_case_side_effects',
                    help_bubble_text=_("When submitting a partial survey, this controls whether the corresponding "
                                       "case should be created, updated or closed.  This is may not be safe to do if "
                                       "the form has not been completed. ")
                ),
                data_bind="visible: submit_partial_forms",
            ),
            crispy.Div(
                'force_surveys_to_use_triggered_case',
                data_bind="visible: isForceSurveysToUsedTriggeredCaseVisible",
            ),
            BootstrapMultiField(
                "",
                InlineField(
                    'use_custom_content_handler',
                    data_bind="checked: use_custom_content_handler",
                ),
                InlineField(
                    'custom_content_handler',
                    css_class="input-xxlarge",
                    data_bind="visible: use_custom_content_handler",
                ),
            ),
            active=False,
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
            'RECIPIENT_USER_GROUP': RECIPIENT_USER_GROUP,
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
            raise ValidationError(_("Please specify a case type."))
        return case_property

    def clean_start_property(self):
        start_reminder_on = self.cleaned_data['start_reminder_on']
        if start_reminder_on == START_REMINDER_ON_CASE_PROPERTY:
            start_property = self.cleaned_data['start_property'].strip()
            if not start_property:
                raise ValidationError(_(
                    "Please enter a case property for the match criteria."
                ))
            return start_property
        if start_reminder_on == START_REMINDER_ALL_CASES:
            return START_PROPERTY_ALL_CASES_VALUE
        return None

    def clean_start_match_type(self):
        start_reminder_on = self.cleaned_data['start_reminder_on']
        if start_reminder_on == START_REMINDER_ON_CASE_PROPERTY:
            return self.cleaned_data['start_match_type']
        if start_reminder_on == START_REMINDER_ALL_CASES:
            return MATCH_ANY_VALUE
        return None

    def clean_start_value(self):
        if (self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_PROPERTY
           and self.cleaned_data['start_match_type'] != MATCH_ANY_VALUE):
            start_value = self.cleaned_data['start_value'].strip()
            if not start_value:
                raise ValidationError(_(
                    "You must specify a value for the case property "
                    "match criteria."
                ))
            return start_value
        return None

    def clean_start_property_offset(self):
        if self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_PROPERTY:
            if self.cleaned_data['start_property_offset_type'] == START_PROPERTY_OFFSET_IMMEDIATE:
                return 0
            start_property_offset = self.cleaned_data['start_property_offset']
            if start_property_offset < 0:
                raise ValidationError(_("Please enter a positive number."))
            return start_property_offset
        return None

    def clean_start_date(self):
        if self.cleaned_data['start_reminder_on'] == START_REMINDER_ON_CASE_DATE:
            start_date = self.cleaned_data['start_date'].strip()
            if not start_date:
                raise ValidationError(_(
                    "You must specify a case property that will provide the "
                    "start date."
                ))
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

    def clean_user_group_id(self):
        if self.cleaned_data['recipient'] == RECIPIENT_USER_GROUP:
            value = self.cleaned_data['user_group_id']
            return clean_group_id(value, self.domain)
        else:
            return None

    def clean_recipient_case_match_property(self):
        if self.cleaned_data['recipient'] == RECIPIENT_SUBCASE:
            case_property = self.cleaned_data['recipient_case_match_property'].strip()
            if not case_property:
                raise ValidationError(_(
                    "You must specify a case property for the case's "
                    "child case."
                ))
            return case_property
        if self.cleaned_data['recipient'] == RECIPIENT_ALL_SUBCASES:
            return '_id'
        return None

    def clean_recipient_case_match_type(self):
        if self.cleaned_data['recipient'] == RECIPIENT_SUBCASE:
            return self.cleaned_data['recipient_case_match_type']
        if self.cleaned_data['recipient'] == RECIPIENT_ALL_SUBCASES:
            return MATCH_ANY_VALUE
        return None

    def clean_case_match_value(self):
        if (self.cleaned_data['recipient'] == RECIPIENT_SUBCASE
           and self.cleaned_data['recipient_case_match_type'] != MATCH_ANY_VALUE):
            match_value = self.cleaned_data['case_match_value'].strip()
            if not match_value:
                raise ValidationError(_("You must provide a value."))
            return match_value
        return None

    def clean_global_timeouts(self):
        global_timeouts = self.cleaned_data['global_timeouts']
        if global_timeouts:
            timeouts_str = global_timeouts.split(",")
            timeouts_int = []
            for t in timeouts_str:
                try:
                    t = int(t.strip())
                    assert t > 0
                    timeouts_int.append(t)
                except (ValueError, AssertionError):
                    raise ValidationError(_(
                        "Timeout intervals must be a list of positive "
                        "numbers separated by commas."
                    ))
            return timeouts_int
        return []

    def clean_events(self):
        method = self.cleaned_data['method']
        try:
            events = json.loads(self.cleaned_data['events'])
        except ValueError:
            raise ValidationError(_(
                "A valid JSON object was not passed in the events input."
            ))

        for event in events:
            eventForm = CaseReminderEventForm(
                data=event,
            )
            if not eventForm.is_valid():
                raise ValidationError(_(
                    "Your event form didn't turn out quite right."
                ))

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
                    raise ValidationError(_("Please provide an SMS message."))

            # clean form_unique_id:
            if method == METHOD_SMS or method == METHOD_SMS_CALLBACK:
                event['form_unique_id'] = None
            else:
                if not event.get('form_unique_id'):
                    raise ValidationError(_(
                        "Please create a form for the survey first, "
                        "and then create the reminder."
                    ))

            fire_time_type = event['fire_time_type']

            # clean fire_time:
            if event['is_immediate'] or fire_time_type == FIRE_TIME_CASE_PROPERTY:
                event['fire_time'] = time()

            # clean fire_time_aux:
            if fire_time_type != FIRE_TIME_CASE_PROPERTY:
                event['fire_time_aux'] = None
            elif not event.get('fire_time_aux'):
                raise ValidationError(_(
                    "Please enter the case property from which to pull "
                    "the time."
                ))

            # clean time_window_length:
            time_window_length = event['time_window_length']
            if fire_time_type != FIRE_TIME_RANDOM:
                event['time_window_length'] = 0
            elif not (0 < time_window_length < 1440):
                raise ValidationError(_(
                    "Window Length must be greater than 0 and less "
                    "than 1440 minutes."
                ))

            # clean day_num:
            if self.ui_type == UI_SIMPLE_FIXED or event['is_immediate']:
                event['day_num'] = 0

            # clean callback_timeout_intervals:
            event['callback_timeout_intervals'] = []
            if (method == METHOD_SMS_CALLBACK
                or method == METHOD_IVR_SURVEY
                or method == METHOD_SMS_SURVEY):
                event['callback_timeout_intervals'] = self.cleaned_data.get(
                    'global_timeouts', [])

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
            raise ValidationError(_("Please enter a positive number."))
        if max_iteration_count == 0:
            raise ValidationError(_(
                "Please enter a number that is 1 or greater."
            ))
        return max_iteration_count

    def clean_until(self):
        if self.cleaned_data['stop_condition'] == STOP_CONDITION_CASE_PROPERTY:
            value = self.cleaned_data['until'].strip()
            if not value:
                raise ValidationError(_(
                    "You must specify a case property for the stop condition."
                ))
            return value
        return None

    def clean_max_question_retries(self):
        value = self.cleaned_data['max_question_retries']
        try:
            value = int(value)
        except ValueError:
            raise ValidationError(_(
                "Max question retries must be an integer."
            ))
        return value

    def clean_force_surveys_to_use_triggered_case(self):
        method = self.cleaned_data['method']
        if method == METHOD_SMS or method == METHOD_SMS_CALLBACK:
            return False
        return self.cleaned_data['force_surveys_to_use_triggered_case']

    def clean_use_custom_content_handler(self):
        if self.is_previewer:
            return self.cleaned_data["use_custom_content_handler"]
        else:
            return self.use_custom_content_handler

    def clean_custom_content_handler(self):
        if self.is_previewer:
            value = self.cleaned_data["custom_content_handler"]
            if self.cleaned_data["use_custom_content_handler"]:
                if value in settings.ALLOWED_CUSTOM_CONTENT_HANDLERS:
                    return value
                else:
                    raise ValidationError(_("Invalid custom content handler."))
            else:
                return None
        else:
            return self.custom_content_handler

    def save(self, reminder_handler):
        if not isinstance(reminder_handler, CaseReminderHandler):
            raise ValueError(_(
                "You must save to a CaseReminderHandler object!"
            ))

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
            'user_group_id',
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
            'force_surveys_to_use_triggered_case',
            'custom_content_handler',
        ]:
            value = self.cleaned_data[field]
            if field == 'recipient' and value == RECIPIENT_ALL_SUBCASES:
                value = RECIPIENT_SUBCASE
            setattr(reminder_handler, field, value)

        start_property_offset = self.cleaned_data['start_property_offset']
        start_date_offset = self.cleaned_data['start_date_offset']
        reminder_handler.start_offset = (start_property_offset
                                         if start_property_offset is not None else start_date_offset)
        reminder_handler.ui_type = self.ui_type
        reminder_handler.domain = self.domain

        reminder_handler.save()

    @classmethod
    def compute_initial(cls, reminder_handler, available_languages):
        initial = {}
        fields = cls.__dict__['base_fields'].keys()
        for field in fields:
            try:
                current_val = getattr(reminder_handler, field, Ellipsis)
                if field == 'events':
                    for event in current_val:
                        messages = dict([(l, '') for l in available_languages])
                        if event.message:
                            for language, text in event.message.items():
                                if language in available_languages:
                                    messages[language] = text
                        event.message = messages
                        if event.form_unique_id:
                            try:
                                form = CCHQForm.get_form(event.form_unique_id)
                                event.form_unique_id = json.dumps({
                                    'text': form.full_path_name,
                                    'id': event.form_unique_id,
                                })
                            except ResourceNotFound:
                                pass
                    current_val = json.dumps([e.to_json() for e in current_val])
                if field == 'callback_timeout_intervals':
                    current_val = ",".join(current_val)
                if (field == 'recipient'
                    and reminder_handler.recipient_case_match_property == '_id'
                    and reminder_handler.recipient_case_match_type == MATCH_ANY_VALUE
                ):
                    current_val = RECIPIENT_ALL_SUBCASES
                if current_val is not Ellipsis:
                    initial[field] = current_val
                if field is 'custom_content_handler' and current_val is not None:
                    initial['use_custom_content_handler'] = True
                if field is 'default_lang' and current_val not in available_languages:
                    initial['default_lang'] = 'en'
            except AttributeError:
                pass

        if reminder_handler.start_date is None:
            if (initial['start_property'] == START_PROPERTY_ALL_CASES_VALUE
                and initial['start_match_type'] == MATCH_ANY_VALUE
            ):
                start_reminder_on = START_REMINDER_ALL_CASES
                del initial['start_property']
                del initial['start_match_type']
            else:
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


class SimpleScheduleCaseReminderForm(BaseScheduleCaseReminderForm):

    def __init__(self, *args, **kwargs):
        super(SimpleScheduleCaseReminderForm, self).__init__(*args, **kwargs)

        event_timing_choices = (
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, EVENT_TIMING_IMMEDIATE),
             _("Immediately When Triggered")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_DEFAULT, None),
             _("At a Specific Time")),
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, None),
             _("Delay After Start")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_CASE_PROPERTY, None),
             _("Time Specific in Case")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_RANDOM, None),
             _("Random Time in Window")),
        )
        event_timing_choices = [(self._format_event_timing_choice(e[0][0], e[0][1], e[0][2]), e[1])
                                for e in event_timing_choices]
        self.fields['event_timing'].choices = event_timing_choices

    @property
    def ui_type(self):
        return UI_SIMPLE_FIXED

    @property
    def section_start_fields(self):
        start_fields = super(SimpleScheduleCaseReminderForm, self).section_start_fields
        start_fields.extend(self.timing_fields)
        return start_fields

    @property
    def section_message_fields(self):
        message_fields = super(SimpleScheduleCaseReminderForm, self).section_message_fields
        message_fields.append(
            crispy.Div(data_bind="template: {name: 'event-template', foreach: eventObjects}")
        )
        return message_fields

    @property
    def timing_fields(self):
        return [
            BootstrapMultiField(
                _("Time of Day"),
                InlineField(
                    'event_timing',
                    data_bind="value: event_timing",
                    css_class="input-xlarge",
                ),
                crispy.Div(
                    style="display: inline;",
                    data_bind="template: {name: 'event-fire-template', foreach: eventObjects}"
                ),
                css_id="timing_block",
                help_bubble_text=_("This controls when the message will be sent. The Time in Case "
                                   "option is useful, for example, if the recipient has chosen a "
                                   "specific time to receive the message.")
            ),
            crispy.Div(
                style="display: inline;",
                data_bind="template: {name: 'event-general-template', foreach: eventObjects}"
            )
        ]


class ComplexScheduleCaseReminderForm(BaseScheduleCaseReminderForm):

    def __init__(self, *args, **kwargs):
        super(ComplexScheduleCaseReminderForm, self).__init__(*args, **kwargs)

        event_timing_choices = (
            ((EVENT_AS_SCHEDULE, FIRE_TIME_DEFAULT, None),
             _("At a Specific Time")),
            ((EVENT_AS_OFFSET, FIRE_TIME_DEFAULT, None),
             _("Delay After Start By")),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_CASE_PROPERTY, None),
             _("Time Specific in Case")
            ),
            ((EVENT_AS_SCHEDULE, FIRE_TIME_RANDOM, None),
             _("Random Time in Window")),
        )
        event_timing_choices = [(self._format_event_timing_choice(e[0][0], e[0][1], e[0][2]), e[1])
                                for e in event_timing_choices]
        self.fields['event_timing'].choices = event_timing_choices

    @property
    def ui_type(self):
        return UI_COMPLEX

    @property
    def section_message_fields(self):
        fields = super(ComplexScheduleCaseReminderForm, self).section_message_fields
        fields = fields[:1] + self.timing_fields + fields[1:]
        fields.append(crispy.Div(template='reminders/partial/complex_message_table.html'))
        return fields

    @property
    def timing_fields(self):
        return [
            BootstrapMultiField(
                _("Time of Day"),
                InlineField(
                    'event_timing',
                    data_bind="value: event_timing",
                    css_class="input-xlarge",
                ),
                css_id="timing_block",
                help_bubble_text=_("This controls when the message will be sent. The Time in Case "
                                   "option is useful, for example, if the recipient has chosen a "
                                   "specific time to receive the message.")
            ),
        ]


class CaseReminderEventForm(forms.Form):
    """
    This form creates or modifies a CaseReminderEvent.
    """
    fire_time_type = forms.ChoiceField(
        choices=(
            (FIRE_TIME_DEFAULT, ugettext_noop("Default")),
            (FIRE_TIME_CASE_PROPERTY, ugettext_noop("Case Property")),  # not valid when method != EVENT_AS_SCHEDULE
            (FIRE_TIME_RANDOM, ugettext_noop("Random")),  # not valid when method != EVENT_AS_SCHEDULE
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
        label=ugettext_noop("HH:MM:SS"),
    )

    # method must be EVENT_AS_SCHEDULE
    fire_time_aux = forms.CharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )

    time_window_length = forms.IntegerField(
        label=ugettext_noop("Window Length (minutes)"),
        required=False
    )

    # messages is visible when the method of the reminder is METHOD_SMS or METHOD_SMS_CALLBACK
    # value will be a dict of {langcode: message}
    message_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    # form_unique_id is visible when the method of the reminder is SMS_SURVEY or IVR_SURVEY
    form_unique_id = forms.CharField(
        required=False,
        label=ugettext_noop("Survey"),
    )

    def __init__(self, ui_type=None, *args, **kwargs):
        super(CaseReminderEventForm, self).__init__(*args, **kwargs)

        self.ui_type = ui_type

        self.helper_fire_time = FormHelper()
        self.helper_fire_time.form_tag = False
        self.helper_fire_time.layout = crispy.Layout(
            crispy.Div(
                template="reminders/partial/fire_time_field.html",
            ),
            crispy.Div(
                InlineField(
                    'fire_time_aux',
                    data_bind="value: fire_time_aux, attr: {id: ''}",
                    css_class="input-large",
                ),
                css_class="help-inline",
                data_bind="visible: isFireTimeAuxVisible",
            ),
        )

        # Note the following is only used for the Simple UI.
        # The Complex UI goes off the template: reminders/partial/complex_message_table.html
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


class CaseReminderEventMessageForm(forms.Form):
    """
    This form specifies the UI for messages in CaseReminderEventForm.
    """
    langcode = forms.CharField(
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
            crispy.Field('langcode', data_bind="value: langcode"),
            BootstrapMultiField(
                '%s <span data-bind="visible: languageLabel()">'
                '(<span data-bind="text:languageLabel"></span>)</span>' %
                _("Message"),
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
    content_type = ChoiceField(choices=(
        (METHOD_SMS, _("SMS Message")),
    ))
    message = TrimmedCharField(required=False)
    form_unique_id = CharField(required=False)

    def __init__(self, *args, **kwargs):
        can_use_survey = kwargs.pop('can_use_survey', False)
        super(OneTimeReminderForm, self).__init__(*args, **kwargs)
        if can_use_survey:
            self.fields['content_type'].choices = CONTENT_CHOICES

    def clean_recipient_type(self):
        return clean_selection(self.cleaned_data.get("recipient_type"))

    def clean_case_group_id(self):
        if self.cleaned_data.get("recipient_type") == RECIPIENT_SURVEY_SAMPLE:
            value = self.cleaned_data.get("case_group_id")
            return clean_case_group_id(value, self._cchq_domain)
        else:
            return None

    def clean_user_group_id(self):
        if self.cleaned_data.get("recipient_type") == RECIPIENT_USER_GROUP:
            value = self.cleaned_data.get("user_group_id")
            return clean_group_id(value, self._cchq_domain)
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

    def render(self, name, value, attrs=None):
        return render_to_string('reminders/partial/record_list_widget.html', {
            'value': value,
            'name': name,
        })

class RecordListField(Field):
    required = None
    label = None
    initial = None
    widget = None
    help_text = None
    
    # When initialized, expects to be passed kwarg input_name, which is the first dot-separated name of all related records in the html form

    def __init__(self, *args, **kwargs):
        input_name = kwargs.pop('input_name')
        kwargs['widget'] = RecordListWidget(attrs={"input_name" : input_name})
        super(RecordListField, self).__init__(*args, **kwargs)

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
    description = TrimmedCharField()
    override_open_sessions = BooleanField(required=False)
    allow_initiation_by_case = BooleanField(required=False)
    allow_initiation_by_mobile_worker = BooleanField(required=False)
    restrict_keyword_initiation = BooleanField(required=False)
    sender_content_type = CharField()
    sender_message = TrimmedCharField(required=False)
    sender_form_unique_id = CharField(required=False)
    notify_others = BooleanField(required=False)
    other_recipient_type = CharField(required=False)
    other_recipient_id = CharField(required=False)
    other_recipient_content_type = CharField(required=False)
    other_recipient_message = TrimmedCharField(required=False)
    other_recipient_form_unique_id = CharField(required=False)
    process_structured_sms = BooleanField(required=False)
    structured_sms_form_unique_id = CharField(required=False)
    use_custom_delimiter = BooleanField(required=False)
    delimiter = TrimmedCharField(required=False)
    use_named_args_separator = BooleanField(required=False)
    use_named_args = BooleanField(required=False)
    named_args_separator = TrimmedCharField(required=False)
    named_args = RecordListField(input_name="named_args")

    def _check_content_type(self, value):
        content_types = [a[0] for a in KEYWORD_CONTENT_CHOICES]
        if value not in content_types:
            raise ValidationError(_("Invalid content type."))
        return value

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values

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

    def clean_restrict_keyword_initiation(self):
        restrict_keyword_initiation = self.cleaned_data.get("restrict_keyword_initiation", False)
        allow_initiation_by_case = self.cleaned_data.get("allow_initiation_by_case", False)
        allow_initiation_by_mobile_worker = self.cleaned_data.get("allow_initiation_by_mobile_worker", False)
        if restrict_keyword_initiation and not (allow_initiation_by_case or allow_initiation_by_mobile_worker):
            raise ValidationError(_("If you are restricting access, please choose at least one type of initiator."))
        return restrict_keyword_initiation

    def clean_sender_content_type(self):
        return self._check_content_type(self.cleaned_data.get("sender_content_type"))

    def clean_sender_message(self):
        value = self.cleaned_data.get("sender_message")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_sender_form_unique_id(self):
        value = self.cleaned_data.get("sender_form_unique_id")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_("Please create a form first, and then add a keyword for it."))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_other_recipient_content_type(self):
        if self.cleaned_data.get("notify_others", False):
            return self._check_content_type(self.cleaned_data.get("other_recipient_content_type"))
        else:
            return None

    def clean_other_recipient_message(self):
        value = self.cleaned_data.get("other_recipient_message")
        if self.cleaned_data.get("notify_others", False) and self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_other_recipient_form_unique_id(self):
        value = self.cleaned_data.get("other_recipient_form_unique_id")
        if self.cleaned_data.get("notify_others", False) and self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_("Please create a form first, and then add a keyword for it."))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_structured_sms_form_unique_id(self):
        value = self.cleaned_data.get("structured_sms_form_unique_id")
        if self.cleaned_data.get("process_structured_sms", False):
            if value is None:
                raise ValidationError(_("Please create a form first, and then add a keyword for it."))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_delimiter(self):
        value = self.cleaned_data.get("delimiter", None)
        if self.cleaned_data.get("process_structured_sms", False) and self.cleaned_data.get("use_custom_delimiter", False):
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_named_args(self):
        if self.cleaned_data.get("process_structured_sms", False) and self.cleaned_data.get("use_named_args", False):
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
        if self.cleaned_data.get("process_structured_sms", False) and self.cleaned_data.get("use_named_args", False) and self.cleaned_data.get("use_named_args_separator", False):
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            if value == self.cleaned_data.get("delimiter"):
                raise ValidationError(_("Delimiter and joining character cannot be the same."))
            return value
        else:
            return None

    def clean_other_recipient_type(self):
        if not self.cleaned_data.get("notify_others", False):
            return None
        value = self.cleaned_data.get("other_recipient_type", None)
        valid_values = [a[0] for a in KEYWORD_RECIPIENT_CHOICES]
        if value not in valid_values:
            raise ValidationError(_("Invalid choice."))
        if value == RECIPIENT_OWNER:
            if not (self.cleaned_data.get("restrict_keyword_initiation") and 
                    self.cleaned_data.get("allow_initiation_by_case") and 
                    not self.cleaned_data.get("allow_initiation_by_mobile_worker")):
                raise ValidationError(_("In order to send to the case's owner you must restrict keyword initiation only to cases."))
        return value

    def clean_other_recipient_id(self):
        if not self.cleaned_data.get("notify_others", False):
            return None
        value = self.cleaned_data.get("other_recipient_id", None)
        recipient_type = self.cleaned_data.get("other_recipient_type", None)
        if recipient_type == RECIPIENT_USER_GROUP:
            try:
                g = Group.get(value)
                assert g.doc_type == "Group"
                assert g.domain == self._cchq_domain
            except Exception:
                raise ValidationError("Invalid Group.")
            return value
        else:
            return None


class NewKeywordForm(Form):
    _cchq_domain = None
    _sk_id = None
    keyword = CharField(label=ugettext_noop("Keyword"))
    description = TrimmedCharField(label=ugettext_noop("Description"))
    override_open_sessions = BooleanField(
        required=False,
        initial=False,
        label=ugettext_noop("Override open SMS Surveys"),
    )
    allow_keyword_use_by = ChoiceField(
        required=False,
        label=ugettext_noop("Allow Keyword Use By"),
        initial='any',
        choices=(
            ('any', ugettext_noop("Both Mobile Workers and Cases")),
            ('users', ugettext_noop("Mobile Workers Only")),
            ('cases', ugettext_noop("Cases Only")),
        )
    )
    sender_content_type = ChoiceField(
        label=ugettext_noop("Send to Sender"),
    )
    sender_message = TrimmedCharField(
        required=False,
        label=ugettext_noop("Message"),
    )
    sender_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    other_recipient_content_type = ChoiceField(
        required=False,
        label=ugettext_noop("Notify Another Person"),
        initial='none',
    )
    other_recipient_id = ChoiceField(
        required=False,
        label=ugettext_noop("Group Name"),
    )
    other_recipient_type = ChoiceField(
        required=False,
        initial=False,
        label=ugettext_noop("Recipient"),
        choices=KEYWORD_RECIPIENT_CHOICES,
    )
    other_recipient_message = TrimmedCharField(
        required=False,
        label=ugettext_noop("Message"),
    )
    other_recipient_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    process_structured_sms = BooleanField(
        required=False,
        label=ugettext_noop("Process incoming keywords as a Structured Message"),
    )
    structured_sms_form_unique_id = ChoiceField(
        required=False,
        label=ugettext_noop("Survey"),
    )
    use_custom_delimiter = BooleanField(
        required=False,
        label=ugettext_noop("Use Custom Delimiter"),
    )
    delimiter = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Delimiter"),
    )
    use_named_args_separator = BooleanField(
        required=False,
        label=ugettext_noop("Use Joining Character"),
    )
    use_named_args = BooleanField(
        required=False,
        label=ugettext_noop("Use Named Answers"),
    )
    named_args_separator = TrimmedCharField(
        required=False,
        label=ugettext_noop("Please Specify Joining Characcter"),
    )
    named_args = RecordListField(
        input_name="named_args",
        initial=[],
    )

    def __init__(self, *args, **kwargs):
        if 'domain' in kwargs:
            self._cchq_domain = kwargs.pop('domain')

        self.process_structured_sms = False
        if 'process_structured' in kwargs:
            self.process_structured_sms = kwargs.pop('process_structured')

        super(NewKeywordForm, self).__init__(*args, **kwargs)

        self.fields['sender_content_type'].choices = self.content_type_choices
        self.fields['other_recipient_content_type'].choices = self.content_type_choices

        self.fields['other_recipient_id'].choices = self.group_choices
        self.fields['sender_form_unique_id'].choices = self.form_choices
        self.fields['other_recipient_form_unique_id'].choices = self.form_choices
        self.fields['structured_sms_form_unique_id'].choices = self.form_choices

        from corehq.apps.reminders.views import KeywordsListView
        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"

        layout_fields = [
            crispy.Fieldset(
                _('Basic Information'),
                crispy.Field(
                    'keyword',
                    data_bind="value: keyword, "
                              "valueUpdate: 'afterkeydown', "
                              "event: {keyup: updateExampleStructuredSMS}",
                ),
                crispy.Field(
                    'description',
                    data_bind="text: description",
                ),
            ),
        ]
        if self.process_structured_sms:
            layout_fields.append(
                crispy.Fieldset(
                    _("Structured Message Options"),
                    crispy.Field(
                        'structured_sms_form_unique_id',
                        data_bind="value: structured_sms_form_unique_id",
                    ),
                    BootstrapMultiField(
                        _("Delimiters"),
                        crispy.Div(
                            InlineColumnField(
                                'use_custom_delimiter',
                                data_bind="checked: use_custom_delimiter, "
                                          "click: updateExampleStructuredSMS",
                                block_css_class="span2",
                            ),
                            InlineField(
                                'delimiter',
                                data_bind="value: delimiter, "
                                          "valueUpdate: 'afterkeydown', "
                                          "event: {keyup: updateExampleStructuredSMS},"
                                          "visible: use_custom_delimiter",
                                block_css_class="span4",
                            ),
                            css_class="controls-row",
                        ),
                    ),
                    BootstrapMultiField(
                        _("Named Answers"),
                        InlineField(
                            'use_named_args',
                            data_bind="checked: use_named_args, "
                                      "click: updateExampleStructuredSMS",
                        ),
                        ErrorsOnlyField('named_args'),
                        crispy.Div(
                            data_bind="template: {"
                                      " name: 'ko-template-named-args', "
                                      " data: $data"
                                      "}, "
                                      "visible: use_named_args",
                        ),
                    ),
                    BootstrapMultiField(
                        _("Joining Characters"),
                        crispy.Div(
                            InlineColumnField(
                                'use_named_args_separator',
                                data_bind="checked: use_named_args_separator, "
                                          "click: updateExampleStructuredSMS",
                                block_css_class="span2",
                            ),
                            InlineField(
                                'named_args_separator',
                                data_bind="value: named_args_separator, "
                                          "valueUpdate: 'afterkeydown', "
                                          "event: {keyup: updateExampleStructuredSMS},"
                                          "visible: useJoiningCharacter",
                                block_css_class="span4",
                            ),
                            css_class="controls-row",
                        ),
                        data_bind="visible: use_named_args",
                    ),
                    BootstrapMultiField(
                        _("Example Structured Message"),
                        crispy.HTML('<pre style="background: white;" '
                                    'data-bind="text: example_structured_sms">'
                                    '</pre>'),
                    ),
                ),
            )
        layout_fields.extend([
            crispy.Fieldset(
                _("Response"),
                crispy.Field(
                    'sender_content_type',
                    data_bind="value: sender_content_type",
                ),
                crispy.Div(
                    crispy.Field(
                        'sender_message',
                        data_bind="text: sender_message",
                    ),
                    data_bind="visible: isMessageSMS",
                ),
                crispy.Div(
                    crispy.Field(
                        'sender_form_unique_id',
                        data_bind="value: sender_form_unique_id"
                    ),
                    data_bind="visible: isMessageSurvey",
                ),
                crispy.Field(
                    'other_recipient_content_type',
                    data_bind="value: other_recipient_content_type",
                ),
                BootstrapMultiField(
                    "",
                    crispy.Div(
                        crispy.HTML(
                            '<h4 style="margin-bottom: 20px;">%s</h4>'
                            % _("Recipient Information"),
                        ),
                        crispy.Field(
                            'other_recipient_type',
                            data_bind="value: other_recipient_type",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_id',
                                data_bind="value: other_recipient_id",
                            ),
                            data_bind="visible: showRecipientGroup",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_message',
                                data_bind="value: other_recipient_message",
                            ),
                            data_bind="visible: other_recipient_content_type() == 'sms'",
                        ),
                        crispy.Div(
                            crispy.Field(
                                'other_recipient_form_unique_id',
                                data_bind="value: other_recipient_form_unique_id",
                            ),
                            data_bind="visible: other_recipient_content_type() == 'survey'",
                        ),
                        css_class="well",
                        data_bind="visible: notify_others",
                    ),
                ),
            ),
            crispy.Fieldset(
                _("Advanced Options"),
                crispy.Field(
                    'override_open_sessions',
                    data_bind="checked: override_open_sessions",
                ),
                'allow_keyword_use_by',
            ),
            FormActions(
                StrictButton(
                    _("Save Keyword"),
                    css_class='btn-primary',
                    type='submit',
                ),
                crispy.HTML('<a href="%s" class="btn">Cancel</a>'
                            % reverse(KeywordsListView.urlname, args=[self._cchq_domain]))
            ),
        ])
        self.helper.layout = crispy.Layout(*layout_fields)

    @property
    def content_type_choices(self):
        choices = [(c[0], c[1]) for c in KEYWORD_CONTENT_CHOICES]
        choices.append(
            ('none', _("No Response"))
        )
        return choices

    @property
    @memoized
    def group_choices(self):
        group_ids = Group.ids_by_domain(self._cchq_domain)
        groups = []
        for group_doc in iter_docs(Group.get_db(), group_ids):
            groups.append((group_doc['_id'], group_doc['name']))
        return groups

    @property
    @memoized
    def form_choices(self):
        available_forms = get_form_list(self._cchq_domain)
        return [(a['code'], a['name']) for a in available_forms]

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            values[field_name] = self[field_name].value()
        return values

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

    def clean_sender_message(self):
        value = self.cleaned_data.get("sender_message")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_sender_form_unique_id(self):
        value = self.cleaned_data.get("sender_form_unique_id")
        if self.cleaned_data.get("sender_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then add a keyword "
                    "for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_other_recipient_message(self):
        value = self.cleaned_data.get("other_recipient_message")
        if self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_other_recipient_form_unique_id(self):
        value = self.cleaned_data.get("other_recipient_form_unique_id")
        if self.cleaned_data.get("other_recipient_content_type") == METHOD_SMS_SURVEY:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then "
                    "add a keyword for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_structured_sms_form_unique_id(self):
        value = self.cleaned_data.get("structured_sms_form_unique_id")
        if self.process_structured_sms:
            if value is None:
                raise ValidationError(_(
                    "Please create a form first, and then add a "
                    "keyword for it."
                ))
            validate_form_unique_id(value, self._cchq_domain)
            return value
        else:
            return None

    def clean_delimiter(self):
        value = self.cleaned_data.get("delimiter", None)
        if self.process_structured_sms and self.cleaned_data["use_custom_delimiter"]:
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_named_args(self):
        if self.process_structured_sms and self.cleaned_data["use_named_args"]:
            use_named_args_separator = self.cleaned_data["use_named_args_separator"]
            value = self.cleaned_data.get("named_args")
            data_dict = {}
            for d in value:
                name = d["name"].strip().upper()
                xpath = d["xpath"].strip()
                if name == "" or xpath == "":
                    raise ValidationError(_(
                        "Name and xpath are both required fields."
                    ))
                for k, v in data_dict.items():
                    if (not use_named_args_separator
                        and (k.startswith(name) or name.startswith(k))
                    ):
                        raise ValidationError(
                            _("Cannot have two names overlap: ") + "(%s, %s)"
                            % (k, name)
                        )
                    if use_named_args_separator and k == name:
                        raise ValidationError(
                            _("Cannot use the same name twice: ") + name
                        )
                    if v == xpath:
                        raise ValidationError(
                            _("Cannot reference the same xpath twice: ") + xpath
                        )
                data_dict[name] = xpath
            return data_dict
        else:
            return {}

    def clean_named_args_separator(self):
        value = self.cleaned_data["named_args_separator"]
        if (self.process_structured_sms
            and self.cleaned_data["use_named_args"]
            and self.cleaned_data["use_named_args_separator"]
        ):
            if value is None or value == "":
                raise ValidationError(_("This field is required."))
            if value == self.cleaned_data["delimiter"]:
                raise ValidationError(_(
                    "Delimiter and joining character cannot be the same."
                ))
            return value
        else:
            return None

    def clean_other_recipient_type(self):
        if self.cleaned_data['other_recipient_content_type'] == 'none':
            return None
        value = self.cleaned_data["other_recipient_type"]
        if value == RECIPIENT_OWNER:
            if self.cleaned_data['allow_keyword_use_by'] != 'cases':
                raise ValidationError(_(
                    "In order to send to the case's owner you must restrict "
                    "keyword initiation only to cases."
                ))
        return value

    def clean_other_recipient_id(self):
        if self.cleaned_data['other_recipient_content_type'] == 'none':
            return None
        value = self.cleaned_data["other_recipient_id"]
        recipient_type = self.cleaned_data.get("other_recipient_type", None)
        if recipient_type == RECIPIENT_USER_GROUP:
            try:
                g = Group.get(value)
                assert g.doc_type == "Group"
                assert g.domain == self._cchq_domain
            except Exception:
                raise ValidationError("Invalid Group.")
            return value
        else:
            return None

