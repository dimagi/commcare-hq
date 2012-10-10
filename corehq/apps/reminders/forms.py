import json
import re
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.forms.fields import *
from django.forms.forms import Form
from django.forms import Field, Widget, Select, TextInput
from django.utils.datastructures import DotExpandedDict
from .models import REPEAT_SCHEDULE_INDEFINITELY, CaseReminderEvent, RECIPIENT_USER, RECIPIENT_CASE, MATCH_EXACT, MATCH_REGEX, MATCH_ANY_VALUE, EVENT_AS_SCHEDULE, EVENT_AS_OFFSET, SurveySample
from dimagi.utils.parsing import string_to_datetime
from dimagi.utils.timezones.forms import TimeZoneChoiceField
from dateutil.parser import parse

METHOD_CHOICES = (
    ('sms', 'SMS'),
    #('email', 'Email'),
    #('test', 'Test'),
    ('survey', 'SMS Survey'),
    ('callback', 'SMS/Callback'),
)

RECIPIENT_CHOICES = (
    (RECIPIENT_USER, "the user whose case matches the rule"),
    (RECIPIENT_CASE, "the case that matches the rule")
)

MATCH_TYPE_DISPLAY_CHOICES = (
    (MATCH_EXACT, "exactly matches"),
    (MATCH_ANY_VALUE, "takes any value"),
    (MATCH_REGEX, "matches the regular expression")
)

START_IMMEDIATELY = "IMMEDIATELY"
START_ON_DATE = "DATE"

START_CHOICES = (
    (START_ON_DATE, "on the date referenced by case property"),
    (START_IMMEDIATELY, "immediately")
)

ITERATE_INDEFINITELY = "INDEFINITE"
ITERATE_FIXED_NUMBER = "FIXED"

ITERATION_CHOICES = (
    (ITERATE_INDEFINITELY, "using the following case property"),
    (ITERATE_FIXED_NUMBER, "after repeating the schedule the following number of times")
)

EVENT_CHOICES = (
    (EVENT_AS_OFFSET, "are offsets from each other"),
    (EVENT_AS_SCHEDULE, "represent the exact day and time in the schedule")
)

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
    method = None
    
    def value_from_datadict(self, data, files, name, *args, **kwargs):
        reminder_events_raw = {}
        for key in data:
            if key[0:16] == "reminder_events.":
                reminder_events_raw[key] = data[key]
        
        event_dict = DotExpandedDict(reminder_events_raw)
        events = []
        if len(event_dict) > 0:
            for key in sorted(event_dict["reminder_events"].iterkeys()):
                events.append(event_dict["reminder_events"][key])
        
        self.method = data["method"]
        
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
        events = []
        for e in value:
            try:
                day = int(e["day"])
            except Exception:
                raise ValidationError("Day must be specified and must be a number.")
            
            pattern = re.compile("\d{1,2}:\d\d")
            if pattern.match(e["time"]):
                try:
                    time = string_to_datetime(e["time"]).time()
                except Exception:
                    raise ValidationError("Please enter a valid time from 00:00 to 23:59.")
            else:
                raise ValidationError("Time must be in the format HH:MM.")
            
            message = {}
            if self.widget.method == "sms" or self.widget.method == "callback":
                for key in e["messages"]:
                    language = e["messages"][key]["language"]
                    text = e["messages"][key]["text"]
                    if len(language.strip()) == 0:
                        raise ValidationError("Please enter a language code.")
                    if len(text.strip()) == 0:
                        raise ValidationError("Please enter a message.")
                    if language in message:
                        raise ValidationError("You have entered the same language twice for the same reminder event.");
                    message[language] = text
            
            if len(e["timeouts"].strip()) == 0 or self.widget.method not in ["callback", "survey"]:
                timeouts_int = []
            else:
                timeouts_str = e["timeouts"].split(",")
                timeouts_int = []
                for t in timeouts_str:
                    try:
                        timeouts_int.append(int(t))
                    except Exception:
                        raise ValidationError("Timeout intervals must be a list of comma-separated numbers.")
            
            form_unique_id = None
            if self.widget.method == "survey":
                form_unique_id = e.get("survey", None)
                if form_unique_id is None:
                    raise ValidationError("Please create a form for the survey first, and then create the reminder definition.")
            
            events.append(CaseReminderEvent(
                day_num = day
               ,fire_time = time
               ,message = message
               ,callback_timeout_intervals = timeouts_int
               ,form_unique_id = form_unique_id
            ))
        
        if len(events) == 0:
            raise ValidationError("You must have at least one reminder event.")
        
        return events

class ComplexCaseReminderForm(Form):
    """
    A form used to create/edit CaseReminderHandlers with any type of schedule.
    """
    nickname = CharField(error_messages={"required":"Please enter the name of this reminder definition."})
    case_type = CharField(error_messages={"required":"Please enter the case type."})
    method = ChoiceField(choices=METHOD_CHOICES, widget=Select(attrs={"onchange":"method_changed();"}))
    recipient = ChoiceField(choices=RECIPIENT_CHOICES)
    start_match_type = ChoiceField(choices=MATCH_TYPE_DISPLAY_CHOICES, widget=Select(attrs={"onchange":"start_match_type_changed();"}))
    start_choice = ChoiceField(choices=START_CHOICES, widget=Select(attrs={"onchange":"start_choice_changed();"}))
    iteration_type = ChoiceField(choices=ITERATION_CHOICES, widget=Select(attrs={"onchange":"iteration_type_changed();"}))
    start_property = CharField(error_messages={"required":"Please enter the name of the case property."})
    start_value = CharField(required=False)
    start_date = CharField(required=False)
    start_offset = IntegerField(error_messages={"required":"Please enter an integer for the day offset.","invalid":"Please enter an integer for the day offset."})
    until = CharField(required=False)
    default_lang = CharField(error_messages={"required":"Please enter the default language to use for the messages."})
    max_iteration_count_input = CharField(required=False)
    max_iteration_count = IntegerField(required=False)
    event_interpretation = ChoiceField(choices=EVENT_CHOICES, widget=Select(attrs={"onchange":"event_interpretation_changed();"}))
    schedule_length = IntegerField()
    events = EventListField()
    
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
        
        
        # Populate events
        events = []
        if "events" in initial:
            for e in initial["events"]:
                ui_event = {
                    "day"       : e.day_num
                   ,"time"      : "%02d:%02d" % (e.fire_time.hour, e.fire_time.minute)
                }
                
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
    
    def clean_max_iteration_count(self):
        if self.cleaned_data.get("iteration_type",None) == ITERATE_FIXED_NUMBER:
            max_iteration_count = self.cleaned_data.get("max_iteration_count_input",None)
        else:
            max_iteration_count = REPEAT_SCHEDULE_INDEFINITELY
        
        try:
            max_iteration_count = int(max_iteration_count)
        except Exception:
            raise ValidationError("Please enter a number greater than zero.")
        
        if max_iteration_count != REPEAT_SCHEDULE_INDEFINITELY and max_iteration_count <= 0:
            raise ValidationError("Please enter a number greater than zero.")
        
        return max_iteration_count

    def clean_start_value(self):
        if self.cleaned_data.get("start_match_type", None) == MATCH_ANY_VALUE:
            return None
        else:
            value = self.cleaned_data.get("start_value")
            if value is None or value == "":
                raise ValidationError("Please enter the value to match.")
            return value

    def clean_start_date(self):
        if self.cleaned_data.get("start_choice", None) == START_IMMEDIATELY:
            return None
        else:
            value = self.cleaned_data.get("start_date")
            if value is None or value == "":
                raise ValidationError("Please enter the name of the case property.")
            return value

    def clean_until(self):
        if self.cleaned_data.get("iteration_type", None) == ITERATE_FIXED_NUMBER:
            return None
        else:
            value = self.cleaned_data.get("until")
            if value is None or value == "":
                raise ValidationError("Please enter the name of the case property.")
            return value
    
    def clean_default_lang(self):
        return self.cleaned_data.get("default_lang").strip()
    
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
        date_regex = re.compile("^\d\d\d\d-\d\d-\d\d$")
        time_regex = re.compile("^\d{1,2}:\d\d(:\d\d){0,1}$")
        for wave_json in value:
            if date_regex.match(wave_json["date"]) is None:
                raise ValidationError("Dates must be in yyyy-mm-dd format.")
            
            if time_regex.match(wave_json["time"]) is None:
                raise ValidationError("Times must be in hh:mm format.")
            
            dt = str(parse(wave_json["date"]).date()) + " " + str(parse(wave_json["time"]).time())
            if datetimes.get(dt, False):
                raise ValidationError("Two waves cannot be scheduled at the same date and time.")
            datetimes[dt] = True
            
            if wave_json["form_id"] == "--choose--":
                raise ValidationError("Please choose a questionnaire.")
        return value
    
    def clean_followups(self):
        value = self.cleaned_data["followups"]
        for followup in value:
            try:
                interval = int(followup["interval"])
            except ValueError:
                raise ValidationError("Follow-up intervals must be positive integers.")
            
            if interval <= 0:
                raise ValidationError("Follow-up intervals must be positive integers.")
            
        return value
    
    def clean_samples(self):
        value = self.cleaned_data["samples"]
        return value

    def clean(self):
        cleaned_data = super(SurveyForm, self).clean()
        return cleaned_data


class SurveySampleForm(Form):
    name = CharField()
    sample_contacts = RecordListField(input_name="sample_contact")
    time_zone = TimeZoneChoiceField()
    
    def clean_sample_contacts(self):
        value = self.cleaned_data["sample_contacts"]
        if len(value) == 0:
            raise ValidationError("Please add at least one contact.");
        for contact in value:
            try:
                contact["phone_number"] = str(int(contact["phone_number"]))
            except ValueError:
                raise ValidationError("Phone numbers must consist only of numbers and must be in international format.")
        return value



