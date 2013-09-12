import re
from django.forms.forms import Form
from django.forms.fields import *
from corehq.apps.sms.models import ForwardingRule, FORWARD_ALL, FORWARD_BY_KEYWORD
from django.core.exceptions import ValidationError
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.reminders.forms import RecordListField
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.sms.util import get_available_backends

FORWARDING_CHOICES = (
    (FORWARD_ALL, ugettext_noop("All messages")),
    (FORWARD_BY_KEYWORD, ugettext_noop("All messages starting with a keyword")),
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
                raise ValidationError(_("This field is required."))
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
            raise ValidationError(_("This field is required."))
        if re.compile("\s").search(value) is not None:
            raise ValidationError(_("Name may not contain any spaces."))

        backend_classes = get_available_backends()
        if self._cchq_domain is None:
            # Ensure name is not duplicated among other global backends
            backend = SMSBackend.view("sms/global_backends", classes=backend_classes, key=[value], include_docs=True).one()
        else:
            # Ensure name is not duplicated among other backends owned by this domain
            backend = SMSBackend.view("sms/backend_by_owner_domain", classes=backend_classes, key=[self._cchq_domain, value], include_docs=True).one()
        if backend is not None and backend._id != self._cchq_backend_id:
            raise ValidationError(_("Name is already in use."))
        
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

class BackendMapForm(Form):
    catchall_backend_id = CharField(required=False)
    backend_map = RecordListField(input_name="backend_map")

    def clean_backend_map(self):
        cleaned_value = {}
        for record in self.cleaned_data.get("backend_map", []):
            prefix = record["prefix"].strip()
            try:
                prefix = int(prefix)
                assert prefix > 0
            except (ValueError, AssertionError):
                raise ValidationError(_("Please enter a positive number for the prefix."))
            prefix = str(prefix)
            if prefix in cleaned_value:
                raise ValidationError(_("Prefix is specified twice:") + prefix)
            cleaned_value[prefix] = record["backend_id"]
        return cleaned_value

    def clean_catchall_backend_id(self):
        value = self.cleaned_data.get("catchall_backend_id", None)
        if value == "":
            return None
        else:
            return value

