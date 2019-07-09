from __future__ import absolute_import
from __future__ import unicode_literals
import re

from crispy_forms.layout import Submit
from django import forms
from django.db.models import Q
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from corehq.apps.hqwebapp.widgets import Select2Ajax
from dimagi.utils.couch.database import iter_docs
from memoized import memoized

from corehq.apps.commtrack.util import generate_code
from corehq.apps.custom_data_fields.edit_entity import (
    CustomDataEditor, get_prefixed, CUSTOM_DATA_FIELD_PREFIX)
from corehq.apps.domain.models import Domain
from corehq.apps.es import UserES
from corehq.apps.locations.permissions import LOCATION_ACCESS_DENIED
from corehq.apps.locations.tasks import make_location_user
from corehq.apps.users.forms import NewMobileWorkerForm, generate_strong_password
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import user_display_string
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.util.quickcache import quickcache

from .models import SQLLocation, LocationType, LocationFixtureConfiguration, LocationRelation
from .permissions import user_can_access_location_id
from .signals import location_edited
from six.moves import filter


class LocationSelectWidget(forms.Widget):
    def __init__(self, domain, attrs=None, id='supply-point', multiselect=False, query_url=None):
        super(LocationSelectWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id
        self.multiselect = multiselect
        if query_url:
            self.query_url = query_url
        else:
            self.query_url = reverse('child_locations_for_select2', args=[self.domain])
        self.template = 'locations/manage/partials/autocomplete_select_widget.html'

    def render(self, name, value, attrs=None, renderer=None):
        location_ids = value or []
        locations = list(SQLLocation.active_objects
                         .filter(domain=self.domain, location_id__in=location_ids))
        initial_data = [{
            'id': loc.location_id,
            'text': loc.get_path_display(),
        } for loc in locations]

        return get_template(self.template).render({
            'id': self.id,
            'name': name,
            'value': [loc.location_id for loc in locations],
            'query_url': self.query_url,
            'multiselect': self.multiselect,
            'initial_data': initial_data,
            'attrs': self.build_attrs(self.attrs, attrs),
        })

    def value_from_datadict(self, data, files, name):
        if self.multiselect:
            return data.getlist(name)
        return super(LocationSelectWidget, self).value_from_datadict(data, files, name)


class ParentLocWidget(forms.Widget):

    def render(self, name, value, attrs=None, renderer=None):
        return get_template(
            'locations/manage/partials/parent_loc_widget.html'
        ).render({
            'name': name,
            'value': value,
            'attrs': self.build_attrs(self.attrs, attrs),
        })


class LocTypeWidget(forms.Widget):

    def render(self, name, value, attrs=None, renderer=None):
        return get_template(
            'locations/manage/partials/loc_type_widget.html'
        ).render({
            'name': name,
            'value': value,
            'attrs': self.build_attrs(self.attrs, attrs),
        })


class LocationForm(forms.Form):
    parent_id = forms.CharField(
        label=ugettext_lazy('Parent'),
        required=False,
        widget=ParentLocWidget(),
    )
    name = forms.CharField(
        label=ugettext_lazy('Name'),
        max_length=255,
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
            return [_f for _f in [
                _("Location Information"),
                'name',
                'location_type' if len(self.get_allowed_types(self.domain, self.location.parent)) > 1 else None,
            ] if _f]
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
            slug_regex = re.compile(r'^[-_\w\d]+$')
            if not slug_regex.match(site_code):
                raise forms.ValidationError(_(
                    'The site code cannot contain spaces or special characters.'
                ))
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
    def get_allowed_types(domain, parent):
        parent_type = parent.location_type if parent else None
        return list(LocationType.objects
                    .filter(domain=domain,
                            parent_type=parent_type)
                    .all())

    def clean_location_type(self):
        loc_type = self.cleaned_data['location_type']
        allowed_types = self.get_allowed_types(self.domain, self.cleaned_data.get('parent'))
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

    def _sync_location_user(self):
        if not self.location.location_id:
            return
        if self.location.location_type.has_user and not self.location.user_id:
            # make sure there's a location user
            res = list(UserES()
                       .domain(self.domain)
                       .show_inactive()
                       .term('user_location_id', self.location.location_id)
                       .values_list('_id', flat=True))
            user_id = res[0] if res else None
            if user_id:
                user = CommCareUser.get(user_id)
            else:
                user = make_location_user(self.location)
            user.is_active = True
            user.user_location_id = self.location.location_id
            user.set_location(self.location, commit=False)
            user.save()
            self.location.user_id = user._id
            self.location.save()
        elif self.location.user_id and not self.location.location_type.has_user:
            # archive the location user
            user = CommCareUser.get_by_user_id(self.location.user_id, self.domain)
            if user:
                user.is_active = False
                user.save()
            self.location.user_id = ''
            self.location.save()

    def save(self, metadata):
        if self.errors:
            raise ValueError('form does not validate')

        location = self.location
        is_new = location.location_id is None

        location.name = self.cleaned_data['name']
        location.site_code = self.cleaned_data['site_code']
        location.location_type = self.cleaned_data['location_type_object']
        location.metadata = metadata or {}
        location.parent = self.cleaned_data['parent']

        coords = self.cleaned_data['coordinates']
        if coords:
            location.latitude = coords[0]
            location.longitude = coords[1]

        location.metadata.update(get_prefixed(self.data, CUSTOM_DATA_FIELD_PREFIX))

        location.save()

        if not is_new:
            self._sync_location_user()
            orig_parent_id = self.cleaned_data.get('orig_parent_id')
            reparented = orig_parent_id is not None
            location_edited.send(sender='loc_mgmt', sql_loc=location,
                                 moved=reparented, previous_parent=orig_parent_id)

        return location


class LocationUserForm(NewMobileWorkerForm):
    def clean_location_id(self):
        # The user form class doesn't handle location. `LocationFormSet` adds
        # the location to the user after.
        return None


class LocationFormSet(object):
    """Ties together the forms for location, location data, user, and user data."""
    _location_form_class = LocationForm
    _location_data_editor = CustomDataEditor
    _user_form_class = LocationUserForm
    _user_data_editor = CustomDataEditor

    def __init__(self, location, request_user, is_new, bound_data=None, *args, **kwargs):
        self.location = location
        self.domain = location.domain
        self.is_new = is_new
        self.request_user = request_user
        self.location_form = self._location_form_class(location, bound_data, is_new=is_new)
        self.custom_location_data = self._get_custom_location_data(bound_data, is_new)

        if self.include_user_forms:
            self.user_form = self._get_user_form(bound_data)
            self.custom_user_data = self._get_custom_user_data(bound_data)
            self.forms = [self.location_form, self.custom_location_data,
                          self.user_form, self.custom_user_data]
        else:
            self.forms = [self.location_form, self.custom_location_data]

    @property
    @memoized
    def include_user_forms(self):
        if not self.is_new:
            return False

        possible_types = LocationForm.get_allowed_types(self.domain, self.location.parent)
        if any(lt.has_user for lt in possible_types):
            if not self.location_form.is_bound:
                # The form hasn't yet been submitted, so we don't know which type
                return True
            else:
                self.location_form.is_valid()
                if 'location_type_object' in self.location_form.cleaned_data:
                    return self.location_form.cleaned_data['location_type_object'].has_user
        return False

    @memoized
    def is_valid(self):
        return all(form.is_valid() for form in self.forms)

    @property
    @memoized
    def errors(self):
        errors = {}
        for form in self.forms:
            errors.update(form.errors)
        return errors

    def save(self):
        if not self.is_valid():
            raise ValueError('Form is not valid')

        if self.include_user_forms:
            self.user.save()
            self.location_form.location.user_id = self.user._id
            location_data = self.custom_location_data.get_data_to_save()
            location = self.location_form.save(metadata=location_data)
            self.user.user_location_id = location.location_id
            self.user.set_location(location)
        else:
            location_data = self.custom_location_data.get_data_to_save()
            location = self.location_form.save(metadata=location_data)

    @property
    @memoized
    def user(self):
        user_data = (self.custom_user_data.get_data_to_save()
                     if self.custom_user_data.is_valid() else {})
        username = self.user_form.cleaned_data.get('username', "")
        password = self.user_form.cleaned_data.get('new_password', "")
        first_name = self.user_form.cleaned_data.get('first_name', "")
        last_name = self.user_form.cleaned_data.get('last_name', "")

        return CommCareUser.create(
            self.domain,
            username,
            password,
            device_id="Generated from HQ",
            first_name=first_name,
            last_name=last_name,
            user_data=user_data,
            commit=False,
        )

    def _get_custom_location_data(self, bound_data, is_new):
        from .views import LocationFieldsView

        existing = self.location.metadata

        # Don't show validation error preemptively on new user creation
        if is_new and bound_data is None:
            existing = None

        custom_data = self._location_data_editor(
            field_view=LocationFieldsView,
            domain=self.domain,
            # For new locations, only display required fields
            required_only=is_new,
            existing_custom_data=existing,
            post_dict=bound_data,
        )
        custom_data.form.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        custom_data.form.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'
        return custom_data

    def _get_user_form(self, bound_data):
        domain_obj = Domain.get_by_name(self.domain)
        form = self._user_form_class(
            project=domain_obj,
            data=bound_data,
            request_user=self.request_user,
            prefix='location_user',
        )

        if domain_obj.strong_mobile_passwords:
            initial_password = generate_strong_password()
            pw_field = crispy.Field(
                'new_password',
                value=initial_password,
            )
        else:
            pw_field = 'new_password'

        form.fields['username'].help_text = None
        form.fields['location_id'].required = False  # This field isn't displayed
        form.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        form.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'
        form.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Location User"),
                'username',
                'first_name',
                'last_name',
                pw_field,
            )
        )
        return form

    def _get_custom_user_data(self, bound_data):
        from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
        user_data = self._user_data_editor(
            field_view=UserFieldsView,
            domain=self.domain,
            post_dict=bound_data,
            required_only=True,
            # Set a different prefix so it's not confused with custom location data
            prefix='user_data',
        )
        return user_data


class UsersAtLocationForm(forms.Form):
    selected_ids = forms.Field(
        label=ugettext_lazy("Workers at Location"),
        required=False,
        widget=Select2Ajax(multiple=True),
    )

    def __init__(self, domain_object, location, *args, **kwargs):
        self.domain_object = domain_object
        self.location = location
        super(UsersAtLocationForm, self).__init__(
            initial={'selected_ids': self.get_users_at_location()},
            prefix="users", *args, **kwargs
        )

        from corehq.apps.reports.filters.api import MobileWorkersOptionsView
        self.fields['selected_ids'].widget.set_url(
            reverse(MobileWorkersOptionsView.urlname, args=(self.domain_object.name,))
        )
        self.fields['selected_ids'].widget.set_initial(self.get_users_at_location())
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Specify Workers at this Location"),
                crispy.Field('selected_ids'),
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    Submit('submit', ugettext_lazy("Update Location Membership"))
                )
            )
        )

    # Adding a 5 second timeout because that is the elasticsearch refresh interval.
    @memoized
    @quickcache(['self.domain_object.name', 'self.location.location_id'], memoize_timeout=0, timeout=5)
    def get_users_at_location(self):
        user_query = UserES().domain(
            self.domain_object.name
        ).mobile_users().location(
            self.location.location_id
        ).fields(['_id', 'username', 'first_name', 'last_name'])
        return [
            dict(id=u['_id'], text=user_display_string(
                u['username'], u.get('first_name', ''), u.get('last_name', '')
            )) for u in user_query.run().hits]

    def unassign_users(self, users):
        for doc in iter_docs(CommCareUser.get_db(), users):
            # This could probably be sped up by bulk saving, but there's a lot
            # of stuff going on - seems tricky.
            CommCareUser.wrap(doc).unset_location_by_id(self.location.location_id, fall_back_to_next=True)

    def assign_users(self, users):
        for doc in iter_docs(CommCareUser.get_db(), users):
            CommCareUser.wrap(doc).add_to_assigned_locations(self.location)

    def clean_selected_ids(self):
        # Django uses get by default, but selected_ids is actually a list
        return self.data.getlist('users-selected_ids')

    def save(self):
        selected_users = set(self.cleaned_data['selected_ids'])
        previous_users = set([u['id'] for u in self.get_users_at_location()])
        to_remove = previous_users - selected_users
        to_add = selected_users - previous_users
        self.unassign_users(to_remove)
        self.assign_users(to_add)
        self.cache_users_at_location(selected_users)

    def cache_users_at_location(self, selected_users):
        user_cache_list = []
        for doc in iter_docs(CommCareUser.get_db(), selected_users):
            display_username = user_display_string(
                doc['username'], doc.get('first_name', ''), doc.get('last_name', ''))
            user_cache_list.append({'text': display_username, 'id': doc['_id']})
        self.get_users_at_location.set_cached_value(self).to(user_cache_list)


class LocationFixtureForm(forms.ModelForm):
    class Meta(object):
        model = LocationFixtureConfiguration
        fields = ['sync_flat_fixture', 'sync_hierarchical_fixture']

    def __init__(self, *args, **kwargs):
        super(LocationFixtureForm, self).__init__(*args, **kwargs)
        self.fields['sync_flat_fixture'].label = _('Sync the flat location fixture (recommended).')
        self.fields['sync_hierarchical_fixture'].label = _(
            'Sync the hierarchicial location fixture (legacy format).'
        )
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-3'
        self.helper.field_class = 'col-sm-3 col-md-3'
        self.helper.layout = crispy.Layout(
            'sync_flat_fixture',
            'sync_hierarchical_fixture',
            StrictButton(
                _("Update Settings"),
                type="submit",
                css_class='btn-primary',
            )
        )


class RelatedLocationForm(forms.Form):
    related_locations = forms.Field(
        label=ugettext_lazy("Related Locations"),
        required=False,
    )

    def __init__(self, domain, location, *args, **kwargs):
        self.location = location
        self.related_location_ids = LocationRelation.from_locations([self.location])
        kwargs['initial'] = {'related_locations': self.related_location_ids}
        super(RelatedLocationForm, self).__init__(*args, **kwargs)

        self.fields['related_locations'].widget = LocationSelectWidget(
            domain, id='id_related_locations', multiselect=True
        )

        locations = (
            SQLLocation.objects
            .filter(location_id__in=self.related_location_ids)
        )

        distance_dict = LocationRelation.relation_distance_dictionary([self.location])

        for loc in locations:
            distance = distance_dict[loc.location_id].get(self.location.location_id)
            self.fields['relation_distance_%s' % loc.location_id] = forms.IntegerField(
                label=ugettext_lazy('{location} Distance').format(location=loc.name),
                required=False, initial=distance
            )

        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

    def clean(self):
        cleaned_data = super(RelatedLocationForm, self).clean()
        for name, value in cleaned_data.items():
            if name.startswith('relation_distance_') and value and value < 0:
                raise forms.ValidationError("The distance cannot be a negative value")

    def save(self):
        selected_location_ids = self.cleaned_data['related_locations']
        selected_location_ids = set(list(filter(None, selected_location_ids)))

        previous_location_ids = self.related_location_ids
        locations_to_remove = previous_location_ids - selected_location_ids

        LocationRelation.objects.filter(
            (Q(location_a=self.location) & Q(location_b__location_id__in=locations_to_remove)) |
            (Q(location_b=self.location) & Q(location_a__location_id__in=locations_to_remove))
        ).delete()

        locations_to_add = selected_location_ids - previous_location_ids
        for location_id in locations_to_add:
            LocationRelation.objects.get_or_create(
                location_a=self.location,
                location_b=SQLLocation.objects.get(location_id=location_id)
            )

        LocationRelation.update_location_distances(
            self.location.location_id,
            {
                name.lstrip('relation_distance'): value
                for name, value in self.cleaned_data.items()
                if name.startswith('relation_distance_')
            }
        )
