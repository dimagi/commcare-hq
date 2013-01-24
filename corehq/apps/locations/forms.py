from django import forms
from corehq.apps.locations.models import Location
from django.template.loader import get_template
from django.template import Template, Context
from corehq.apps.locations.util import load_locs_json

class ParentLocWidget(forms.Widget):
    def render(self, name, value, attrs=None):
        return get_template('locations/manage/partials/parent_loc_widget.html').render(Context({
                    'name': name,
                    'value': value,
                    'locations': load_locs_json(self.domain, value),
                }))

class LocTypeWidget(forms.Widget):
    def render(self, name, value, attrs=None):
        return get_template('locations/manage/partials/loc_type_widget.html').render(Context({
                    'name': name,
                    'value': value,
                }))


class LocationForm(forms.Form):
    parent_id = forms.CharField(label='Parent', required=False, widget=ParentLocWidget())
    name = forms.CharField(max_length=100)
    location_type = forms.CharField(label='Type', widget=LocTypeWidget())

    def __init__(self, location, *args, **kwargs):
        self.location = location
        kwargs['initial'] = self.location._doc
        try:
            kwargs['initial']['parent_id'] = self.location.lineage[0]
        except Exception:
            pass

        super(LocationForm, self).__init__(*args, **kwargs)

        self.fields['parent_id'].widget.domain = self.location.domain

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
