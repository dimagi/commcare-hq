from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import VERSION_CHOICES


class FacilityRegistryForm(forms.Form):
    """Form to create or update a FacilityRegistry document."""

    name = forms.CharField(
        label="Name/description",
        required=True)

    url = forms.URLField(
        label="Endpoint URL (including version)",
        required=True)

    version = forms.ChoiceField(
        label="Facility Registry API version",
        choices=VERSION_CHOICES,
        initial=(1, 0))

    username = forms.CharField(
        label="API username")

    password = forms.CharField(
        label="API password")

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.add_input(Submit('submit', 'Submit'))

        forms.Form.__init__(self, *args, **kwargs)


class FacilityForm(forms.Form):
    """Form to update a Facility."""

    name = forms.CharField(
        label="Facility Name")

    active = forms.BooleanField(
        label="Active")

    # todo: identifiers, extended properties

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.add_input(Submit('submit', 'Submit'))

        forms.Form.__init__(self, *args, **kwargs)
