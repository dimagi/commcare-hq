from django.forms.forms import Form
from django.forms.fields import *
from corehq.apps.sms.models import ForwardingRule, FORWARD_ALL, FORWARD_BY_KEYWORD
from django.core.exceptions import ValidationError

FORWARDING_CHOICES = (
    (FORWARD_ALL, "All messages"),
    (FORWARD_BY_KEYWORD, "All messages starting with a keyword"),
)

class ForwardingRuleForm(Form):
    forward_type = ChoiceField(choices=FORWARDING_CHOICES)
    keyword = CharField(required=False)
    backend_id = CharField()
    
    def clean_keyword(self):
        forward_type = self.cleaned_data.get("forward_type")
        keyword = self.cleaned_data.get("keyword", "").strip()
        if forward_type == FORWARD_BY_KEYWORD:
            if keyword == "":
                raise ValidationError("This field is required.")
            return keyword
        else:
            return None

class BackendForm(Form):
    name = CharField()
    authorized_domains = CharField(required=False)

    def clean_authorized_domains(self):
        value = self.cleaned_data.get("authorized_domains")
        return [domain.strip() for domain in value.split(",")]

