from django.core.urlresolvers import reverse
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.db.utils import ProgrammingError
from django.conf import settings
from crispy_forms import layout as crispy
from crispy_forms.layout import Layout
from crispy_forms.helper import FormHelper
from crispy_forms.bootstrap import StrictButton
from corehq.apps.hqwebapp import crispy as hqcrispy
from custom.rch.models import AreaMapping


def get_choices_for(value_field, display_field):
    """
    return a tuple of tuples with value and display text for each unique available option for
    display field
    for ex: return all combinations for state code and state name for all unique state names
    available
    :param value_field: column for value
    :param display_field: column for display text
    :return: tuple of tuples
    """
    if settings.UNIT_TESTING:
        return tuple()
    options = set()
    try:
        possible_display_values = AreaMapping.objects.values_list(display_field, flat=True).distinct()
        for display_value in possible_display_values:
            option_values = (
                AreaMapping.objects.filter(**{display_field: display_value})
                .values_list(value_field, flat=True).distinct()
            )
            for option_value in option_values:
                options.add((option_value, display_value))
        return tuple(options)
    # when migrations are run for the first time to add AreaMapping table this would
    # fail with Programming Error when loading environment for migration so just pass
    # then. When the web server/worker would be started migrations would have run already
    # and the proper values would be set
    except ProgrammingError:
        return tuple()


class BeneficiariesFilterForm(forms.Form):
    stcode = forms.ChoiceField(
        label=_("State"),
        required=False,
        choices=get_choices_for('stcode', 'stname'),
    )

    dtcode = forms.ChoiceField(
        label=_("District"),
        required=False,
        choices=get_choices_for('dtcode', 'dtname'),
    )

    awcid = forms.ChoiceField(
        label=_("AWC-ID"),
        required=False,
        choices=((('', _('Select One')),) + get_choices_for('awcid', 'awcid'))
    )

    village_code = forms.ChoiceField(
        label=_("Village"),
        required=False,
        choices=((('', _('Select One')),) + get_choices_for('village_code', 'village_name'))
    )

    present_in = forms.ChoiceField(
        label=_("Present In"),
        required=False,
        choices=(('both', 'Both'), ('cas', 'ICDS-CAS'), ('rch', 'RCH'))
    )

    beneficiary_type = forms.ChoiceField(
        label=_("Beneficiary Type"),
        required=False,
        choices=(('mother', 'Mother'), ('child', 'Child'))
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
            crispy.Fieldset(
                _('Filter'),
                crispy.Field('stcode'),
                crispy.Field('dtcode'),
                crispy.Field('village_code'),
                crispy.Field('awcid'),
                crispy.Field('present_in'),
                crispy.Field('beneficiary_type'),
                crispy.Field('matched'),
            ),
            hqcrispy.FormActions(
                hqcrispy.LinkButton(_("Clear"),
                                    reverse(BeneficariesList.urlname, args=[domain]),
                                    css_class="btn btn-default"),
                StrictButton(_("Submit"),
                             type="submit",
                             css_class='btn btn-success disable-on-submit-no-spinner add-spinner-on-click'),
            ),
        )
