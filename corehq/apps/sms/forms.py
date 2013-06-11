import re
from django.forms.forms import Form
from django.forms.fields import *
from corehq.apps.sms.models import ForwardingRule, FORWARD_ALL, FORWARD_BY_KEYWORD
from django.core.exceptions import ValidationError
from corehq.apps.sms.mixin import SMSBackend

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
    _cchq_domain = None
    _cchq_backend_id = None
    name = CharField()
    give_other_domains_access = BooleanField(required=False)
    authorized_domains = CharField(required=False)
    reply_to_phone_number = CharField(required=False)

    def clean_name(self):
        value = self.cleaned_data.get("name")
        if value is not None:
            value = value.strip().upper()
        if value is None or value == "":
            raise ValidationError("This field is required.")
        if re.compile("\s").search(value) is not None:
            raise ValidationError("Name may not contain any spaces.")
        
        backend = SMSBackend.view("sms/backend_by_owner_domain", key=[self._cchq_domain, value], include_docs=True).one()
        if backend is not None and backend._id != self._cchq_backend_id:
            raise ValidationError("Name is already in use.")
        
        return value

    def clean_authorized_domains(self):
        if not self.cleaned_data.get("give_other_domains_access"):
            return []
        else:
            value = self.cleaned_data.get("authorized_domains")
            if value is None or value.strip() == "":
                return []
            else:
                return [domain.strip() for domain in value.split(",")]

    def clean_reply_to_phone_number(self):
        value = self.cleaned_data.get("reply_to_phone_number")
        if value is None:
            return None
        else:
            value = value.strip()
            if value == "":
                return None
            else:
                return value

