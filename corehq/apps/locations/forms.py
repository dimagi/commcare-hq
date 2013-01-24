from django import forms
from corehq.apps.locations.models import Location
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

class LocationForm(forms.Form):
    name = forms.CharField(max_length=100)
    location_type = forms.CharField(max_length=50)
    parent_id = forms.CharField(required=False)

    def __init__(self, location, *args, **kwargs):
        self.location = location
        kwargs['initial'] = self.location._doc
        try:
            kwargs['initial']['parent_id'] = self.location.lineage[0]
        except Exception:
            pass

        self.helper = FormHelper()
        self.helper.form_id = 'location'
        self.helper.form_class = 'form form-horizontal'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Update' if self.location._id else 'Create'))

        super(LocationForm, self).__init__(*args, **kwargs)

    def save(self, instance=None, commit=True):
        if self.errors:
            raise ValueError('form does not validate')

        location = instance or self.location

        for field in ('name', 'location_type'):
            setattr(location, field, self.cleaned_data[field])
        location.lineage = Location(parent=self.cleaned_data['parent_id']).lineage

        if commit:
            location.save()

        return location

