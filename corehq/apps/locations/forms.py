import json
from django import forms
from corehq.apps.locations.models import Location
from django.template.loader import get_template
from django.template import Context
from corehq.apps.locations.util import load_locs_json, allowed_child_types, location_custom_properties, lookup_by_property
from django.utils.safestring import mark_safe
from corehq.apps.locations.signals import location_created, location_edited
from django.utils.translation import ugettext as _
import re

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
    location_type = forms.CharField(widget=LocTypeWidget())
    coordinates = forms.CharField(max_length=30, required=False,
                                  help_text="enter as 'lat lon' or 'lat, lon' (e.g., '42.3652 -71.1029')")
    site_code = forms.CharField(
        label='Site Code',
        required=False,
        help_text=_("A unique system code for this location. Leave this blank to have it auto generated")
    )

    strict = True # optimization hack: strict or loose validation 
    def __init__(self, location, bound_data=None, *args, **kwargs):
        self.location = location

        kwargs['prefix'] = 'main'
        # seed form data from couch doc
        kwargs['initial'] = dict(self.location._doc)
        kwargs['initial']['parent_id'] = self.cur_parent_id
        lat, lon = (getattr(self.location, k, None) for k in ('latitude', 'longitude'))
        kwargs['initial']['coordinates'] = '%s, %s' % (lat, lon) if lat is not None else ''

        super(LocationForm, self).__init__(bound_data, *args, **kwargs)
        self.fields['parent_id'].widget.domain = self.location.domain

        # custom properties
        self.sub_forms = {}
        # TODO think i need to change this to iterate over all types, since the parent
        # can be changed dynamically
        for potential_type in allowed_child_types(self.location.domain, self.location.parent):
            subform = LocationCustomPropertiesSubForm(self.location, potential_type, bound_data)
            if subform.fields:
                self.sub_forms[potential_type] = subform

    @property
    def cur_parent_id(self):
        try:
            return self.location.lineage[0]
        except Exception:
            return None

    def clean_parent_id(self):
        parent_id = self.cleaned_data['parent_id']
        if not parent_id:
            parent_id = None # normalize ''
        parent = Location.get(parent_id) if parent_id else None
        self.cleaned_data['parent'] = parent

        if self.location._id is not None and self.cur_parent_id != parent_id:
            # location is being re-parented

            if parent and self.location._id in parent.path:
                assert False, 'location being re-parented to self or descendant'

            if self.location.descendants:
                raise forms.ValidationError('only locations that have no sub-locations can be moved to a different parent')

            self.cleaned_data['orig_parent_id'] = self.cur_parent_id

        return parent_id

    def clean_name(self):
        name = self.cleaned_data['name']

        if self.strict:
            siblings = self.location.siblings(self.cleaned_data.get('parent'))
            if name in [loc.name for loc in siblings]:
                raise forms.ValidationError('name conflicts with another location with this parent')

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
            raise forms.ValidationError('another location already uses this site code')

        return site_code

    def clean_location_type(self):
        loc_type = self.cleaned_data['location_type']

        child_types = allowed_child_types(self.location.domain, self.cleaned_data.get('parent'))

        if not child_types:
            assert False, 'the selected parent location cannot have sub-locations!'
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

    def clean(self):
        super(LocationForm, self).clean()

        subform = self.sub_forms.get(self.cleaned_data.get('location_type'))
        if subform:
            if not subform.is_valid():
                raise forms.ValidationError('Error in location properties')
            self.cleaned_data.update(('prop:%s' % k, v) for k, v in subform.cleaned_data.iteritems())

        self.cleaned_data['metadata'] = json.loads(self.data['metadata']) \
            if self.data.get('metadata', None) else {}

        return self.cleaned_data

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
        location.lineage = Location(parent=self.cleaned_data['parent_id']).lineage
        location.metadata = self.cleaned_data.get('metadata', {})

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
            location_edited.send(sender='loc_mgmt', loc=location, moved=reparented)

        if reparented:
            # post-location move processing here
            # (none for now; do it as a batch job)
            pass

        return location

class LocationCustomPropertiesSubForm(forms.Form):
    def __init__(self, location, potential_type, *args, **kwargs):
        self.location = location
        self.properties = location_custom_properties(location.domain, potential_type)

        kwargs['prefix'] = 'props_%s' % potential_type
        super(LocationCustomPropertiesSubForm, self).__init__(*args, **kwargs)

        for p in self.properties:
            self.fields[p.name] = p.field(getattr(location, p.name, None))

    def __getattr__(self, attr):
        for p in self.properties:
            if attr == 'clean_%s' % p.name:
                def clean_custom():
                    try:
                        val = self.cleaned_data[p.name]
                        if val is not None:
                            p.custom_validate(self.location, val, p.name)
                        return val
                    except Exception, e:
                        raise forms.ValidationError(mark_safe(str(e)))
                return clean_custom
        raise AttributeError
