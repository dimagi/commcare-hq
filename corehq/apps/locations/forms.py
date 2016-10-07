import re

from django import forms
from django.db.models import Q
from django.template import Context
from django.template.loader import get_template
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.commtrack.util import generate_code
from corehq.apps.custom_data_fields import CustomDataEditor
from corehq.apps.custom_data_fields.edit_entity import get_prefixed
from corehq.apps.es import UserES
from corehq.apps.users.forms import MultipleSelectionForm
from corehq.apps.locations.permissions import LOCATION_ACCESS_DENIED
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import raw_username, user_display_string

from .models import SQLLocation, LocationType
from .permissions import user_can_access_location_id
from .signals import location_edited


class ParentLocWidget(forms.Widget):

    def render(self, name, value, attrs=None):
        return get_template(
            'locations/manage/partials/parent_loc_widget.html'
        ).render(Context({
            'name': name,
            'value': value,
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
        label=ugettext_lazy('Parent'),
        required=False,
        widget=ParentLocWidget(),
    )
    name = forms.CharField(
        label=ugettext_lazy('Name'),
        max_length=100,
    )
    location_type = forms.CharField(
        label=ugettext_lazy('Organization Level'),
        required=False,
        widget=LocTypeWidget(),
    )
    coordinates = forms.CharField(
        label=ugettext_lazy('Coordinates'),
        max_length=30,
        required=False,
        help_text=ugettext_lazy("enter as 'lat lon' or 'lat, lon' "
                                "(e.g., '42.3652 -71.1029')"),
    )
    site_code = forms.CharField(
        label='Site Code',
        required=False,
        help_text=ugettext_lazy("A unique system code for this location. "
                                "Leave this blank to have it auto generated"),
    )
    external_id = forms.CharField(
        label='External ID',
        required=False,
        help_text=ugettext_lazy("A number referencing this location on an external system")
    )
    external_id.widget.attrs['readonly'] = True

    strict = True  # optimization hack: strict or loose validation

    def __init__(self, location, bound_data=None, is_new=False, user=None,
                 *args, **kwargs):
        self.location = location
        self.domain = location.domain
        self.user = user
        self.is_new_location = is_new

        kwargs['initial'] = {
            'parent_id': location.parent_location_id,
            'name': location.name,
            'site_code': location.site_code,
            'external_id': location.external_id,
        }
        if not self.is_new_location:
            kwargs['initial']['location_type'] = self.location.location_type.name
        kwargs['initial']['parent_id'] = self.location.parent_location_id
        lat, lon = (getattr(self.location, k, None)
                    for k in ('latitude', 'longitude'))
        kwargs['initial']['coordinates'] = ('%s, %s' % (lat, lon)
                                            if lat is not None else '')

        self.custom_data = self.get_custom_data(bound_data, is_new)

        self.custom_data.form.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.custom_data.form.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        super(LocationForm, self).__init__(bound_data, *args, **kwargs)
        self.fields['parent_id'].widget.domain = self.domain
        self.fields['parent_id'].widget.user = user

        if not self.location.external_id:
            self.fields['external_id'].widget = forms.HiddenInput()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(*self.get_fields(is_new))
        )

    def get_fields(self, is_new):
        if is_new:
            return filter(None, [
                _("Location Information"),
                'name',
                'location_type' if len(self._get_allowed_types(self.domain, self.location.parent)) > 1 else None,
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
            domain=self.domain,
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
        if self.is_new_location:
            parent = self.location.parent
            parent_id = self.location.parent_location_id
        else:
            parent_id = self.cleaned_data['parent_id'] or None
            parent = SQLLocation.objects.get(location_id=parent_id) if parent_id else None

        if self.user and not user_can_access_location_id(self.domain, self.user, parent_id):
            raise forms.ValidationError(LOCATION_ACCESS_DENIED)

        self.cleaned_data['parent'] = parent

        if self.location.location_id is not None and self.location.parent_location_id != parent_id:
            # location is being re-parented

            if parent and self.location.location_id in parent.path:
                raise forms.ValidationError(_("Location's parent is itself or a descendant"))

            if self.location.get_descendants().exists():
                raise forms.ValidationError(_(
                    'only locations that have no child locations can be '
                    'moved to a different parent'
                ))

            self.cleaned_data['orig_parent_id'] = self.location.parent_location_id

        return parent_id

    def clean_name(self):
        def has_siblings_with_name(location, name, parent_location_id):
            qs = SQLLocation.objects.filter(domain=location.domain,
                                            name=name)
            if parent_location_id:
                qs = qs.filter(parent__location_id=parent_location_id)
            else:  # Top level
                qs = qs.filter(parent=None)
            return (qs.exclude(location_id=self.location.location_id)
                      .exists())

        name = self.cleaned_data['name']
        parent_location_id = self.cleaned_data.get('parent_id', None)

        if self.strict:
            if has_siblings_with_name(self.location, name, parent_location_id):
                raise forms.ValidationError(_(
                    'name conflicts with another location with this parent'
                ))

        return name

    def clean_site_code(self):
        site_code = self.cleaned_data['site_code']

        if site_code:
            site_code = site_code.lower()
            if (SQLLocation.objects.filter(domain=self.domain,
                                        site_code__iexact=site_code)
                                   .exclude(location_id=self.location.location_id)
                                   .exists()):
                raise forms.ValidationError(_(
                    'another location already uses this site code'
                ))
            return site_code

    def clean(self):
        if 'name' in self.cleaned_data and not self.cleaned_data.get('site_code', None):
            all_codes = [
                code.lower() for code in
                (SQLLocation.objects.exclude(location_id=self.location.location_id)
                                    .filter(domain=self.domain)
                                    .values_list('site_code', flat=True))
            ]
            self.cleaned_data['site_code'] = generate_code(self.cleaned_data['name'], all_codes)

    @staticmethod
    def _get_allowed_types(domain, parent):
        parent_type = parent.location_type if parent else None
        return list(LocationType.objects
                    .filter(domain=domain,
                            parent_type=parent_type)
                    .all())

    def clean_location_type(self):
        loc_type = self.cleaned_data['location_type']
        allowed_types = self._get_allowed_types(self.domain, self.cleaned_data.get('parent'))
        if not allowed_types:
            raise forms.ValidationError(_('The selected parent location cannot have child locations!'))

        if not loc_type:
            if len(allowed_types) == 1:
                loc_type_obj = allowed_types[0]
            else:
                raise forms.ValidationError(_('You must select a location type'))
        else:
            try:
                loc_type_obj = (LocationType.objects
                                .filter(domain=self.domain)
                                .get(Q(code=loc_type) | Q(name=loc_type)))
            except LocationType.DoesNotExist:
                raise forms.ValidationError(_("LocationType '{}' not found").format(loc_type))
            else:
                if loc_type_obj not in allowed_types:
                    raise forms.ValidationError(_('Location type not valid for the selected parent.'))

        self.cleaned_data['location_type_object'] = loc_type_obj
        return loc_type_obj.name

    def clean_coordinates(self):
        coords = self.cleaned_data['coordinates'].strip()
        if not coords:
            return None
        pieces = re.split('[ ,]+', coords)

        if len(pieces) != 2:
            raise forms.ValidationError(_('could not understand coordinates'))

        try:
            lat = float(pieces[0])
            lon = float(pieces[1])
        except ValueError:
            raise forms.ValidationError(_('could not understand coordinates'))

        return [lat, lon]

    def save(self, instance=None, commit=True):
        if self.errors:
            raise ValueError('form does not validate')

        location = instance or self.location
        is_new = location.location_id is None

        location.name = self.cleaned_data['name']
        location.site_code = self.cleaned_data['site_code']
        location.location_type = self.cleaned_data['location_type_object']
        location.metadata = self.custom_data.get_data_to_save()
        location.parent = self.cleaned_data['parent']

        coords = self.cleaned_data['coordinates']
        if coords:
            location.latitude = coords[0]
            location.longitude = coords[1]

        location.metadata.update(get_prefixed(self.data))

        if commit:
            location.save()

        if not is_new:
            orig_parent_id = self.cleaned_data.get('orig_parent_id')
            reparented = orig_parent_id is not None
            location_edited.send(sender='loc_mgmt', sql_loc=location,
                                 moved=reparented, previous_parent=orig_parent_id)

        return location


class UsersAtLocationForm(MultipleSelectionForm):

    def __init__(self, domain_object, location, *args, **kwargs):
        self.domain_object = domain_object
        self.location = location
        super(UsersAtLocationForm, self).__init__(
            initial={'selected_ids': self.users_at_location},
            *args, **kwargs
        )
        self.fields['selected_ids'].choices = self.get_all_users()
        self.fields['selected_ids'].label = ugettext_lazy("Workers at Location")

    def get_all_users(self):
        user_query = (UserES()
                      .domain(self.domain_object.name)
                      .mobile_users()
                      .fields(['_id', 'username', 'first_name', 'last_name']))
        return [
            (u['_id'], user_display_string(u['username'],
                                           u.get('first_name', ''),
                                           u.get('last_name', '')))
            for u in user_query.run().hits
        ]

    @property
    @memoized
    def users_at_location(self):
        user_query = (UserES()
                      .domain(self.domain_object.name)
                      .mobile_users()
                      .location(self.location.location_id)
                      .fields([]))
        return user_query.run().doc_ids

    def unassign_users(self, users):
        for doc in iter_docs(CommCareUser.get_db(), users):
            # This could probably be sped up by bulk saving, but there's a lot
            # of stuff going on - seems tricky.
            CommCareUser.wrap(doc).unset_location_by_id(self.location.location_id, fall_back_to_next=True)

    def assign_users(self, users):
        for doc in iter_docs(CommCareUser.get_db(), users):
            CommCareUser.wrap(doc).add_to_assigned_locations(self.location)

    def save(self):
        selected_users = set(self.cleaned_data['selected_ids'])
        previous_users = set(self.users_at_location)
        to_remove = previous_users - selected_users
        to_add = selected_users - previous_users

        self.unassign_users(to_remove)
        self.assign_users(to_add)
