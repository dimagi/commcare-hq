from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit

from custom.rch.models import AreaMapping


def get_state_names_choices():
    states = AreaMapping.objects.order_by().values_list('stname', flat=True).distinct()
    options = set()
    for state in states:
        options.add((state, state))
    return tuple(options)


def get_district_names_choices():
    districts = AreaMapping.objects.order_by().values_list('dtname', flat=True).distinct()
    options = set()
    for district in districts:
        options.add((district, district))
    return tuple(options)


def get_awcids_choices():
    awcids = AreaMapping.objects.order_by().values_list('awcid', flat=True).distinct()
    options = set()
    for awcid in awcids:
        options.add((awcid, awcid))
    return tuple(options)


def get_village_codes_choices():
    village_codes = AreaMapping.objects.order_by().values_list('villcode', flat=True).distinct()
    options = set()
    for village_code in village_codes:
        options.add((village_code, village_code))
    return tuple(options)


def get_village_names():
    village_names = AreaMapping.objects.order_by('Village_name').values_list('Village_name', flat=True).distinct()
    options = set()
    for village_name in village_names:
        options.add((village_name, village_name))
    return tuple(options)


class BeneficiariesFilterForm(forms.Form):
    state = forms.ChoiceField(
        label=ugettext_lazy("State"),
        required=True,
        choices=get_state_names_choices()
    )

    district = forms.ChoiceField(
        label=ugettext_lazy("District"),
        required=True,
        choices=get_district_names_choices()
    )

    awcid = forms.ChoiceField(
        label=ugettext_lazy("AWC-ID"),
        required=True,
        choices=get_awcids_choices()
    )

    village_id = forms.ChoiceField(
        label=ugettext_lazy("Village-ID"),
        required=True,
        choices=get_village_codes_choices()
    )

    village_name = forms.ChoiceField(
        label=ugettext_lazy("Village Name"),
        required=True,
        choices=get_village_names()
    )

    def __init__(self, *args, **kwargs):
        super(BeneficiariesFilterForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.form_name = 'Filter:'
        self.helper.label_class = 'col-sm-2 col-md-1'
        self.helper.field_class = 'col-sm-4 col-md-3'
        self.helper.layout = Layout(
            crispy.Field(
                'state',
            ),
            crispy.Field(
                'district'
            ),
            crispy.Field(
                'awcid'
            ),
            crispy.Field(
                'village_id'
            ),
            crispy.Field(
                'village_name'
            ),
            ButtonHolder(
                Submit('submit', 'Submit', css_class='button white')
            )
        )
