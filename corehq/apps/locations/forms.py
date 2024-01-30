import re

from django import forms
from django.template.loader import get_template
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from memoized import memoized

from dimagi.utils.couch.database import iter_docs

from corehq.apps.custom_data_fields.edit_entity import (
    CUSTOM_DATA_FIELD_PREFIX,
    CustomDataEditor,
    get_prefixed,
)
from corehq.apps.es import UserES
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import Select2Ajax, SelectToggle
from corehq.apps.locations.permissions import LOCATION_ACCESS_DENIED
from corehq.apps.locations.util import (
    validate_site_code,
    generate_site_code,
    has_siblings_with_name,
    get_location_type
)
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import user_display_string
from corehq.util.quickcache import quickcache

from .models import (
    LocationFixtureConfiguration,
    LocationType,
    SQLLocation,
)
from .permissions import user_can_access_location_id
from .signals import location_edited
from crispy_forms.utils import flatatt


class LocationSelectWidget(forms.Widget):
    def __init__(self, domain, attrs=None, id='supply-point', multiselect=False, placeholder=None):
        super(LocationSelectWidget, self).__init__(attrs)
        self.domain = domain
        self.id = id
        self.multiselect = multiselect
        self.placeholder = placeholder
        self.query_url = reverse('location_search', args=[self.domain])
        self.template = 'locations/manage/partials/autocomplete_select_widget.html'

    def render(self, name, value, attrs=None, renderer=None):
        location_ids = to_list(value) if value else []
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
            'placeholder': self.placeholder,
            'initial_data': initial_data,
            'attrs': flatatt(self.build_attrs(self.attrs, attrs)),
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
        label=gettext_lazy('Parent'),
        required=False,
        widget=ParentLocWidget(),
    )
    name = forms.CharField(
        label=gettext_lazy('Name'),
        max_length=255,
    )
    location_type = forms.CharField(
        label=gettext_lazy('Organization Level'),
        required=False,
        widget=LocTypeWidget(),
    )
    coordinates = forms.CharField(
        label=gettext_lazy('Coordinates'),
        max_length=30,
        required=False,
        help_text=gettext_lazy("enter as 'lat lon' or 'lat, lon' "
                               "(e.g., '42.3652 -71.1029')"),
    )
    site_code = forms.CharField(
        label='Site Code',
        required=False,
        help_text=gettext_lazy("A unique system code for this location. "
                               "Leave this blank to have it auto generated"),
    )
    external_id = forms.CharField(
        label='External ID',
        required=False,
        help_text=gettext_lazy("A number referencing this location on an external system")
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

            self.cleaned_data['orig_parent_id'] = self.location.parent_location_id

        return parent_id

    def clean_name(self):
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
            return validate_site_code(self.domain, self.location.location_id, site_code, forms.ValidationError)

    def clean(self):
        if 'name' in self.cleaned_data and not self.cleaned_data.get('site_code', None):
            self.cleaned_data['site_code'] = generate_site_code(
                self.domain, self.location.location_id, self.cleaned_data['name'])

    @staticmethod
    def get_allowed_types(domain, parent):
        parent_type = parent.location_type if parent else None
        return list(LocationType.objects
                    .filter(domain=domain,
                            parent_type=parent_type)
                    .all())

    def clean_location_type(self):
        loc_type_obj = get_location_type(self.domain, self.location, self.cleaned_data.get('parent'),
                                         self.cleaned_data['location_type'], forms.ValidationError,
                                         self.is_new_location)
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
        if self.location.user_id:
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


class LocationFormSet(object):
    """Ties together the forms for location, location data, user, and user data."""
    _location_form_class = LocationForm
    _location_data_editor = CustomDataEditor

    def __init__(self, location, request, is_new, bound_data=None, *args, **kwargs):
        self.location = location
        self.domain = location.domain
        self.is_new = is_new
        self.request = request
        self.request_user = request.couch_user
        self.location_form = self._location_form_class(location, bound_data, is_new=is_new)
        self.custom_location_data = self._get_custom_location_data(bound_data, is_new)
        self.forms = [self.location_form, self.custom_location_data]

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

        location_data = self.custom_location_data.get_data_to_save()
        self.location_form.save(metadata=location_data)

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


class UsersAtLocationForm(forms.Form):
    selected_ids = forms.Field(
        label=gettext_lazy("Workers at Location"),
        required=False,
        widget=Select2Ajax(multiple=True),
    )

    def __init__(self, request, domain_object, location, *args, **kwargs):
        self.request = request
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
                    Submit('submit', gettext_lazy("Update Location Membership"))
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
        from corehq.apps.users.views.utils import log_commcare_user_locations_changes

        selected_users = set(self.cleaned_data['selected_ids'])
        previous_users = set([u['id'] for u in self.get_users_at_location()])
        to_remove = previous_users - selected_users
        to_add = selected_users - previous_users
        users_to_be_updated = set.union(to_add, to_remove)

        # fetch before updates and fetch from Couch to avoid any ES lag
        targeted_users_old_locations = {
            user_doc['_id']: {
                'location_id': user_doc['location_id'],
                'assigned_location_ids': user_doc['assigned_location_ids']
            }
            for user_doc in iter_docs(CommCareUser.get_db(), users_to_be_updated)
        }

        self.unassign_users(to_remove)
        self.assign_users(to_add)
        self.cache_users_at_location(selected_users)

        # re-fetch users to get fresh locations
        for updated_user_doc in iter_docs(CommCareUser.get_db(), users_to_be_updated):
            updated_user = CommCareUser.wrap_correctly(updated_user_doc)
            user_old_locations = targeted_users_old_locations[updated_user.get_id]
            log_commcare_user_locations_changes(
                self.request, updated_user,
                old_location_id=user_old_locations['location_id'],
                old_assigned_location_ids=user_old_locations['assigned_location_ids'])

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


class LocationFilterForm(forms.Form):
    ACTIVE = 'active'
    ARCHIVED = 'archived'
    SHOW_ALL = 'show_all'

    LOCATION_ACTIVE_STATUS = (
        (SHOW_ALL, gettext_lazy('Show All')),
        (ACTIVE, gettext_lazy('Only Active')),
        (ARCHIVED, gettext_lazy('Only Archived'))
    )

    location_id = forms.CharField(
        label=gettext_noop("Location"),
        required=False,
    )
    selected_location_only = forms.BooleanField(
        required=False,
        label=_('Only include selected location'),
        initial=False,
    )
    location_status_active = forms.ChoiceField(
        label=_('Active / Archived'),
        choices=LOCATION_ACTIVE_STATUS,
        required=False,
        widget=SelectToggle(choices=LOCATION_ACTIVE_STATUS, attrs={"ko_value": "location_status_active"}),
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['location_id'].widget = LocationSelectWidget(
            self.domain,
            id='id_location_id',
            placeholder=_("All Locations"),
            attrs={'data-bind': 'value: location_id'},
        )
        self.fields['location_id'].widget.query_url = "{url}?show_all=true".format(
            url=self.fields['location_id'].widget.query_url
        )

        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_method = 'GET'
        self.helper.form_id = 'locations-filters'
        self.helper.form_action = reverse('location_export', args=[self.domain])

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Filter and Download Locations"),
                crispy.Field('location_id',),
                crispy.Div(
                    crispy.Field('selected_location_only', data_bind='checked: selected_location_only'),
                    data_bind="slideVisible: location_id",
                ),
                crispy.Field('location_status_active',),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Download Locations"),
                    type="submit",
                    css_class="btn btn-primary",
                    data_bind="html: buttonHTML",
                ),
            ),
        )

    def clean_location_id(self):
        if self.cleaned_data['location_id'] == '':
            return None
        return self.cleaned_data['location_id']

    def clean_location_status_active(self):
        location_active_status = self.cleaned_data['location_status_active']

        if location_active_status == self.ACTIVE:
            return True
        if location_active_status == self.ARCHIVED:
            return False
        return None

    def is_valid(self):
        if not super().is_valid():
            return False
        location_id = self.cleaned_data.get('location_id')
        if location_id is None:
            return True
        return user_can_access_location_id(self.domain, self.user, location_id)

    def get_filters(self):
        """
        This function translates some form inputs to their relevant SQLLocation attributes
        """
        location_id = self.cleaned_data.get('location_id')
        if (
            location_id
            and user_can_access_location_id(self.domain, self.user, location_id)
        ):
            location_ids = [location_id]
        else:
            location_ids = []

        filters = {
            'location_ids': location_ids,
            'selected_location_only': self.cleaned_data.get('selected_location_only', False)
        }
        location_status_active = self.cleaned_data.get('location_status_active', None)

        if location_status_active is not None:
            filters['is_archived'] = (not location_status_active)

        return filters


def to_list(value):
    """
    Returns ``value`` as a list if it is iterable and not a string,
    otherwise returns ``value`` in a list.

    >>> to_list(('foo', 'bar', 'baz'))
    ['foo', 'bar', 'baz']
    >>> to_list('foo bar baz')
    ['foo bar baz']

    """
    if hasattr(value, '__iter__') and not isinstance(value, str):
        return list(value)
    return [value]
