from __future__ import absolute_import
from __future__ import unicode_literals
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django import forms
from django_countries.data import COUNTRIES
from django.utils.translation import ugettext_lazy as _
from corehq.apps.sms.models import INCOMING, OUTGOING, SQLMobileBackend
from phonenumbers import country_code_for_region


class PublicSMSRateCalculatorForm(forms.Form):
    country_code = forms.ChoiceField(label='Country')

    def __init__(self, *args, **kwargs):
        super(PublicSMSRateCalculatorForm, self).__init__(*args, **kwargs)

        isd_codes = []
        countries = sorted(list(COUNTRIES.items()), key=lambda x: x[1].encode('utf-8'))
        for country_shortcode, country_name in countries:
            country_isd_code = country_code_for_region(country_shortcode)
            isd_codes.append((country_isd_code, country_name))

        self.fields['country_code'].choices = isd_codes

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_action = 'post'
        self.helper.layout = crispy.Layout(
            crispy.Field(
                'country_code',
                css_class="input-xxlarge hqwebapp-select2",
                data_bind="value: country_code",
                placeholder=_("Please Select a Country Code"),
            ),
        )


class SMSRateCalculatorForm(forms.Form):
    gateway = forms.ChoiceField(label="Connection")
    country_code = forms.ChoiceField(label="Country Code")
    direction = forms.ChoiceField(label="Direction", choices=(
        (OUTGOING, _("Outgoing")),
        (INCOMING, _("Incoming")),
    ))

    def __init__(self, domain, *args, **kwargs):
        super(SMSRateCalculatorForm, self).__init__(*args, **kwargs)
        backends = SQLMobileBackend.get_domain_backends(SQLMobileBackend.SMS, domain)

        def _get_backend_info(backend):
            return backend.couch_id, "%s (%s)" % (backend.name, backend.hq_api_id)

        backends = [_get_backend_info(g) for g in backends]
        self.fields['gateway'].choices = backends

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Field(
                'gateway',
                data_bind="value: gateway, event: {change: clearSelect2}",
                css_class="input-xxlarge",
            ),
            crispy.Field(
                'direction', data_bind="value: direction, "
                                       "event: {change: clearSelect2}",
            ),
            crispy.Field(
                'country_code',
                css_class="input-xxlarge",
                data_bind="value: select2CountryCode.value, "
                          "event: {change: updateRate}",
            ),
        )
