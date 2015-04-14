import re

from django import forms
from django.template import Context
from django.template.loader import get_template
from django.utils.translation import ugettext as _

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.custom_data_fields import CustomDataEditor

from .models import Location
from .signals import location_created, location_edited
from .util import load_locs_json, allowed_child_types, lookup_by_property


class ParentLocWidget(forms.Widget):
    def render(self, name, value, attrs=None):
        return get_template(
            'locations/manage/partials/parent_loc_widget.html'
        ).render(Context({
            'name': name,
            'value': value,
            'locations': load_locs_json(self.domain, value),
        }))


class LocTypeWidget(forms.Widget):
    def render(self, name, value, attrs=None):
        return get_template(
            'locations/manage/partials/loc_type_widget.html'
        ).render(Context({
            'name': name,
            'value': value,
        }))


class LocationForm(forms.Form):
    parent_id = forms.CharField(
        label=_('Parent'),
        required=False,
        widget=ParentLocWidget(),
    )
    name = forms.CharField(max_length=100)
    location_type = forms.CharField(widget=LocTypeWidget(), required=False)
    coordinates = forms.CharField(
        max_length=30,
        required=False,
        help_text=_("enter as 'lat lon' or 'lat, lon' "
                    "(e.g., '42.3652 -71.1029')"),
    )
    site_code = forms.CharField(
        label='Site Code',
        required=False,
        help_text=_("A unique system code for this location. "
                    "Leave this blank to have it auto generated"),
    )
    external_id = forms.CharField(
        label='External ID',
        required=False,
        help_text=_("A number referencing this location on an external system")
    )
    external_id.widget.attrs['readonly'] = True

    strict = True  # optimization hack: strict or loose validation

    def __init__(self, location, bound_data=None, is_new=False,
                 *args, **kwargs):
        self.location = location

        # seed form data from couch doc
        kwargs['initial'] = dict(self.location._doc)
        kwargs['initial']['parent_id'] = self.location.parent_id
        lat, lon = (getattr(self.location, k, None)
                    for k in ('latitude', 'longitude'))
        kwargs['initial']['coordinates'] = ('%s, %s' % (lat, lon)
                                            if lat is not None else '')

        self.custom_data = self.get_custom_data(bound_data, is_new)

        super(LocationForm, self).__init__(bound_data, *args, **kwargs)
        self.fields['parent_id'].widget.domain = self.location.domain

        if not self.location.external_id:
            self.fields['external_id'].widget = forms.HiddenInput()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(*self.get_fields(is_new))
        )

    def get_fields(self, is_new):
        if is_new:
            parent = (Location.get(self.location.parent_id)
                      if self.location.parent_id else None)
            child_types = allowed_child_types(self.location.domain, parent)
            return filter(None, [
                _("Location Information"),
                'name',
                'location_type' if len(child_types) > 1 else None,
            ])
        else:
            return [
                _("Location Information"),
                'name',
                'parent_id',
                'location_type',
                'coordinates',
                'site_code',
                'external_id',
            ]

    def get_custom_data(self, bound_data, is_new):
        from .views import LocationFieldsView

        existing = self.location.metadata

        # Don't show validation error preemptively on new user creation
        if is_new and bound_data is None:
            existing = None

        return CustomDataEditor(
            field_view=LocationFieldsView,
            domain=self.location.domain,
            # For new locations, only display required fields
            required_only=is_new,
            existing_custom_data=existing,
            post_dict=bound_data,
        )

    def is_valid(self):
        return all([
            super(LocationForm, self).is_valid(),
            self.custom_data.is_valid(),
        ])

    @property
    def errors(self):
        errors = super(LocationForm, self).errors
        errors.update(self.custom_data.errors)
        return errors

    def clean_parent_id(self):
        parent_id = self.cleaned_data['parent_id'] or self.location.parent_id
        parent = Location.get(parent_id) if parent_id else None
        self.cleaned_data['parent'] = parent

        if self.location._id is not None and self.location.parent_id != parent_id:
            # location is being re-parented

            if parent and self.location._id in parent.path:
                assert False, 'location being re-parented to self or descendant'

            if self.location.descendants:
                raise forms.ValidationError(
                    'only locations that have no child locations can be '
                    'moved to a different parent'
                )

            self.cleaned_data['orig_parent_id'] = self.location.parent_id

        return parent_id

    def clean_name(self):
        name = self.cleaned_data['name']

        if self.strict:
            siblings = self.location.siblings(self.cleaned_data.get('parent'))
            if name in [loc.name for loc in siblings]:
                raise forms.ValidationError(
                    'name conflicts with another location with this parent'
                )

        return name

    def clean_site_code(self):
        site_code = self.cleaned_data['site_code']

        if site_code:
            site_code = site_code.lower()

        lookup = lookup_by_property(
            self.location.domain,
            'site_code',
            site_code,
            'global'
        )
        if lookup and lookup != set([self.location._id]):
            raise forms.ValidationError(
                'another location already uses this site code'
            )

        return site_code

    def clean_location_type(self):
        loc_type = self.cleaned_data['location_type']

        child_types = allowed_child_types(self.location.domain,
                                          self.cleaned_data.get('parent'))
        if not loc_type:
            if len(child_types) == 1:
                return child_types[0]
            assert False, 'You must select a location type'

        if not child_types:
            assert False, \
                'the selected parent location cannot have child locations!'
        elif loc_type not in child_types:
            assert False, 'not valid for the select parent location'

        return loc_type

    def clean_coordinates(self):
        coords = self.cleaned_data['coordinates'].strip()
        if not coords:
            return None
        pieces = re.split('[ ,]+', coords)

        if len(pieces) != 2:
            raise forms.ValidationError('could not understand coordinates')

        try:
            lat = float(pieces[0])
            lon = float(pieces[1])
        except ValueError:
            raise forms.ValidationError('could not understand coordinates')

        return [lat, lon]

    def save(self, instance=None, commit=True):
        if self.errors:
            raise ValueError('form does not validate')

        location = instance or self.location
        is_new = location._id is None

        for field in ('name', 'location_type', 'site_code'):
            setattr(location, field, self.cleaned_data[field])
        coords = self.cleaned_data['coordinates']
        setattr(location, 'latitude', coords[0] if coords else None)
        setattr(location, 'longitude', coords[1] if coords else None)
        location.lineage = Location(
            parent=self.cleaned_data['parent_id']
        ).lineage
        location.metadata = self.custom_data.get_data_to_save()

        for k, v in self.cleaned_data.iteritems():
            if k.startswith('prop:'):
                prop_name = k[len('prop:'):]
                setattr(location, prop_name, v)

        orig_parent_id = self.cleaned_data.get('orig_parent_id')
        reparented = orig_parent_id is not None
        if reparented:
            location.flag_post_move = True
            location.previous_parents.append(orig_parent_id)

        if commit:
            location.save()

        if is_new:
            location_created.send(sender='loc_mgmt', loc=location)
        else:
            location_edited.send(sender='loc_mgmt',
                                 loc=location,
                                 moved=reparented)

        if reparented:
            # post-location move processing here
            # (none for now; do it as a batch job)
            pass

        return location
