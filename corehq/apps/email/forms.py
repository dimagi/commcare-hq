import copy
import re

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.layout import Div
from django import forms
from django.forms import CharField, ChoiceField
from django.forms.forms import Form
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, gettext_noop

from corehq.apps.email.models import SQLEmailSMTPBackend
from corehq.apps.email.util import get_email_backend_classes
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.userreports.exceptions import ValidationError
from corehq.apps.users.models import CouchUser


class InitiateAddEmailBackendForm(Form):
    action = CharField(
        initial='new_backend',
        widget=forms.HiddenInput(),
    )
    hq_api_id = ChoiceField(
        required=False,
        label="Gateway Type",
    )

    def __init__(self, user: CouchUser, *args, **kwargs):
        domain = kwargs.pop('domain', None)
        super(InitiateAddEmailBackendForm, self).__init__(*args, **kwargs)

        backend_choices = []
        backend_choices = sorted(backend_choices, key=lambda backend: backend[1])
        self.fields['hq_api_id'].choices = backend_choices

        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            hqcrispy.B3MultiField(
                _("Create Another Gateway"),
                InlineField('action'),
                Div(InlineField('hq_api_id', css_class="ko-select2"), css_class='col-sm-6 col-md-6 col-lg-4'),
                Div(StrictButton(
                    mark_safe('<i class="fa fa-plus"></i> Add Another Gateway'),  # nosec: no user input
                    css_class='btn-primary',
                    type='submit',
                    style="margin-left:5px;"
                ), css_class='col-sm-3 col-md-2 col-lg-2'),
            ),
        )

    def backend_classes_for_domain(self, domain):
        backends = copy.deepcopy(get_email_backend_classes())
        return backends


class BackendForm(Form):
    domain = None
    backend_id = None
    name = CharField(
        label=gettext_noop("Name"),
        required=True,
    )
    display_name = CharField(
        label=gettext_noop("Display Name"),
        required=False,
    )
    description = CharField(
        label=gettext_noop("Description"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        required=False,
    )
    username = CharField(
        label=gettext_noop("Username"),
        required=True,
    )
    password = CharField(
        label=gettext_noop("Password"),
        required=True,
    )
    server = CharField(
        label=gettext_noop("Server"),
        required=True,
    )
    port = CharField(
        label=gettext_noop("Port"),
        required=True,
    )

    @property
    def general_fields(self):
        fields = [
            crispy.Field('name', css_class='input-xxlarge'),
            crispy.Field('display_name', css_class='input-xxlarge'),
            crispy.Field('description', css_class='input-xlarge'),
            crispy.Field('username', css_class='input-xxlarge'),
            crispy.Field('password', css_class='input-xxlarge'),
            crispy.Field('server', css_class='input-xxlarge'),
            crispy.Field('port', css_class='input-xxlarge'),
        ]

        return fields

    def __init__(self, *args, **kwargs):
        button_text = kwargs.pop('button_text', _("Create Email Gateway"))
        self.domain = kwargs.pop('domain')
        self.backend_id = kwargs.pop('backend_id')
        super(BackendForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('General Settings'),
                *self.general_fields
            ),
            self.gateway_specific_fields,
            # crispy.Fieldset(
            #     _("Phone Numbers"),
            #     crispy.Div(
            #         data_bind="template: {"
            #                   " name: 'ko-load-balancing-template', "
            #                   " data: $data"
            #                   "}",
            #     ),
            #     data_bind="visible: use_load_balancing",
            # ),
            hqcrispy.FormActions(
                StrictButton(
                    button_text,
                    type="submit",
                    css_class='btn-primary'
                ),
            ),
        )

        if self.backend_id:
            #   When editing, don't allow changing the name because name might be
            # referenced as a contact-level backend preference.
            #   By setting disabled to True, Django makes sure the value won't change
            # even if something else gets posted.
            self.fields['name'].disabled = True

    @property
    def gateway_specific_fields(self):
        return crispy.Div()

    def clean_name(self):
        value = self.cleaned_data.get("name")
        if value is not None:
            value = value.strip().upper()
        if value is None or value == "":
            raise ValidationError(_("This field is required."))
        if re.compile(r"\s").search(value) is not None:
            raise ValidationError(_("Name may not contain any spaces."))

        is_unique = SQLEmailSMTPBackend.name_is_unique(
            value,
            domain=self.domain,
            backend_id=self.backend_id
        )

        if not is_unique:
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

    def clean_opt_out_keywords(self):
        keywords = self.cleaned_data.get('opt_out_keywords')
        if not keywords:
            return []
        else:
            return [kw.strip().upper() for kw in keywords.split(',')]

    def clean_opt_in_keywords(self):
        keywords = self.cleaned_data.get('opt_in_keywords')
        if not keywords:
            return []
        else:
            return [kw.strip().upper() for kw in keywords.split(',')]

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
