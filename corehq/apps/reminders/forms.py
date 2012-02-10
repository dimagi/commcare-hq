import json
from django.core.exceptions import ValidationError
from django.forms.fields import *
from django.forms.forms import Form

METHOD_CHOICES = (
    ('sms', 'SMS'),
    ('email', 'Email'),
    ('test', 'Test'),
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
