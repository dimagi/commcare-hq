import json
import re
from django.core.exceptions import ValidationError
from django.forms.fields import *
from django.forms.forms import Form
from django.forms import Field, Widget
from django.utils.datastructures import DotExpandedDict
from .models import REPEAT_SCHEDULE_INDEFINITELY, CaseReminderEvent
from dimagi.utils.parsing import string_to_datetime

METHOD_CHOICES = (
    ('sms', 'SMS'),
    #('email', 'Email'),
    #('test', 'Test'),
    ('callback', 'Callback')
)

"""
A form used to create/edit CaseReminderHandlers.
"""
class CaseReminderForm(Form):
    nickname = CharField()
    case_type = CharField()
#    method = ChoiceField(choices=METHOD_CHOICES)
    default_lang = CharField()
#    lang_property = CharField()
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
            for key in sorted(event_dict["reminder_events"].iterkeys()):
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
            for key in e["messages"]:
                language = e["messages"][key]["language"]
                text = e["messages"][key]["text"]
                if len(language.strip()) == 0:
                    raise ValidationError("Please enter a language code.")
                if len(text.strip()) == 0:
                    raise ValidationError("Please enter a message.")
                message[language] = text
            
            if len(e["timeouts"].strip()) == 0:
                timeouts_int = []
            else:
                timeouts_str = e["timeouts"].split(",")
                timeouts_int = []
                for t in timeouts_str:
                    try:
                        timeouts_int.append(int(t))
                    except Exception:
                        raise ValidationError("Callback timeout intervals must be a list of comma-separated numbers.")
            
            events.append(CaseReminderEvent(
                day_num = day
               ,fire_time = time
               ,message = message
               ,callback_timeout_intervals = timeouts_int
            ))
            
        return events

class ComplexCaseReminderForm(Form):
    nickname = CharField()
    case_type = CharField()
    method = ChoiceField(choices=METHOD_CHOICES)
    start = CharField()
    start_offset = IntegerField()
    until = CharField()
    default_lang = CharField()
    iteration_type = CharField()
    max_iteration_count_input = CharField(required=False)
    max_iteration_count = IntegerField(required=False)
    event_interpretation = CharField()
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
                ui_event["messages"] = messages
                
                timeouts_str = []
                for t in e.callback_timeout_intervals:
                    timeouts_str.append(str(t))
                ui_event["timeouts"] = ",".join(timeouts_str)
                
                events.append(ui_event)
        
        self.initial["events"] = events
    
    def clean_max_iteration_count(self):
        if self.cleaned_data.get("iteration_type",None) == "FIXED":
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




