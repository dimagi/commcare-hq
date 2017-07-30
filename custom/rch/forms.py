from django.core.urlresolvers import reverse
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.db.utils import ProgrammingError
from crispy_forms import layout as crispy
from crispy_forms.layout import Layout, ButtonHolder, Submit, HTML
from crispy_forms.helper import FormHelper

from custom.rch.models import AreaMapping


def get_choices_for(value_field, field_name):
    options = set()
    try:
        field_values = AreaMapping.objects.values_list(field_name, flat=True).distinct()
        for field_value in field_values:
            option_values = (
                AreaMapping.objects.filter(**{field_name: field_value})
                .values_list(value_field, flat=True).distinct()
            )
            for option_value in option_values:
                options.add((option_value, field_value))
    except ProgrammingError:
        pass
    return tuple(options)


class BeneficiariesFilterForm(forms.Form):
    stcode = forms.ChoiceField(
        label=_("State"),
        required=False,
        choices=get_choices_for('stcode', 'stname'),
        disabled=True
    )

    dtcode = forms.ChoiceField(
        label=_("District"),
        required=False,
        choices=get_choices_for('dtcode', 'dtname'),
        disabled=True
    )

    awcid = forms.ChoiceField(
        label=_("AWC-ID"),
        required=False,
        choices=((('', _('Select One')),) + get_choices_for('awcid', 'awcid'))
    )

    village_code = forms.ChoiceField(
        label=_("Village-ID"),
        required=False,
        choices=((('', _('Select One')),) + get_choices_for('village_code', 'village_name'))
    )

    present_in = forms.ChoiceField(
        label=_("Present In"),
        required=False,
        choices=(('both', 'Both'), ('cas', 'ICDS-CAS'), ('rch', 'RCH'))
    )

    matched = forms.BooleanField(
        label=_("Include matched beneficiaries"),
        required=False,
        help_text="Include matched beneficiaries when filtering for beneficiaries just in "
                  "ICDS-CAS or RCH"
    )

    def __init__(self, domain, *args, **kwargs):
        from custom.rch.views import BeneficariesList
        super(BeneficiariesFilterForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.form_name = 'Filter:'
        self.helper.label_class = 'col-sm-2 col-md-1'
        self.helper.field_class = 'col-sm-4 col-md-3'
        self.helper.form_method = 'GET'
        self.helper.layout = Layout(
            crispy.Field(
                'stcode',
            ),
            crispy.Field(
                'dtcode'
            ),
            crispy.Field(
                'village_code'
            ),
            crispy.Field(
                'awcid'
            ),
            crispy.Field(
                'present_in'
            ),
            crispy.Field(
                'matched'
            ),
            ButtonHolder(
                Submit('submit', 'Submit', css_class='button white pull-left')
            ),
            ButtonHolder(
                HTML('<a href="{}" class="btn btn-primary">{}</a>'.format(
                    reverse(BeneficariesList.urlname, args=[domain]),
                    _('Clear')))
            ),
        )
