import json
import logging

from django.contrib import messages
from django.core.cache import cache
from django.http import Http404, HttpResponseRedirect
from django.http.response import HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.views.decorators.http import require_http_methods

from memoized import memoized

from dimagi.utils.couch import get_redis_lock, release_lock
from dimagi.utils.web import json_response
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context

from corehq import toggles
from corehq.apps.commtrack.util import unicode_slug
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.custom_data_fields.edit_model import CustomDataModelMixin
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.crispy import make_form_readonly
from corehq.apps.hqwebapp.decorators import use_jquery_ui, use_multiselect
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.hqwebapp.views import no_permissions
from corehq.apps.locations.const import LOCK_LOCATIONS_TIMEOUT
from corehq.apps.locations.permissions import location_safe
from corehq.apps.locations.tasks import (
    download_locations_async,
    import_locations_async,
)
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.reports.filters.api import EmwfOptionsView
from corehq.apps.reports.filters.controllers import EmwfOptionsController
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.users.forms import MultipleSelectionForm
from corehq.util import reverse
from corehq.util.files import file_extention_from_filename
from corehq.util.workbook_json.excel import WorkbookJSONError, get_workbook

from .analytics import users_have_locations
from .const import ROOT_LOCATION_TYPE
from .dbaccessors import get_users_assigned_to_locations
from .exceptions import LocationConsistencyError
from .forms import (
    LocationFilterForm,
    LocationFormSet,
    UsersAtLocationForm,
)
from .models import LocationType, SQLLocation, filter_for_archived
from .permissions import (
    can_edit_location,
    can_edit_location_types,
    can_edit_or_view_location,
    locations_access_required,
    require_can_edit_locations,
    require_can_edit_or_view_locations,
    user_can_edit_location_types,
)
from .tree_utils import assert_no_cycles
from .util import load_locs_json, location_hierarchy_config
from django.http import JsonResponse, HttpResponseBadRequest
from corehq.apps.locations.dbaccessors import get_filtered_locations_count

logger = logging.getLogger(__name__)


@location_safe
@locations_access_required
def default(request, domain):
    if request.couch_user.can_edit_locations():
        return HttpResponseRedirect(reverse(LocationsListView.urlname, args=[domain]))
    elif user_can_edit_location_types(request.couch_user, domain):
        return HttpResponseRedirect(reverse(LocationTypesView.urlname, args=[domain]))
    return no_permissions(request)


def lock_locations(func):
    # Decorate a post/delete method of a view to ensure concurrent locations edits don't happen.
    def func_wrapper(request, *args, **kwargs):
        key = "import_locations_async-{domain}".format(domain=request.domain)
        lock = get_redis_lock(
            key,
            timeout=LOCK_LOCATIONS_TIMEOUT,
            name="import_locations_async",
        )
        if lock.acquire(blocking=False):
            try:
                return func(request, *args, **kwargs)
            finally:
                release_lock(lock, True)
        else:
            message = _("Some of the location edits are still in progress, "
                        "please wait until they finish and then try again")
            messages.warning(request, message)
            if request.method == 'DELETE':
                # handle delete_location view
                return json_response({'success': False, 'message': message})
            else:
                return HttpResponseRedirect(request.META['HTTP_REFERER'])

    return func_wrapper


def import_locations_task_key(domain):
    # cache key to track download_id of import_locations_async task
    return 'import_locations_async-task-status-{domain}'.format(domain=domain)


def pending_location_import_download_id(domain):
    # Check if there is an unfinished import_locations_async
    # If the task is pending returns download_id of the task else returns False
    key = import_locations_task_key(domain)
    download_id = cache.get(key)
    if download_id:
        try:
            context = get_download_context(download_id)
        except TaskFailedError:
            return False
        if context['is_ready']:
            return False
        else:
            # task hasn't finished
            return download_id
    else:
        return False


def check_pending_locations_import(redirect=False):
    """
    Decorate any location edit View with this, to warn user to not edit if a location upload is
        under process
    If redirect is set to True, user is redirected to current location import status page
    """
    def _outer(view_fn):
        def new_fn(request, domain, *args, **kwargs):
            download_id = pending_location_import_download_id(domain)
            if download_id:
                status_url = reverse('location_import_status', args=[domain, download_id])
                if redirect:
                    # redirect to import status page
                    return HttpResponseRedirect(status_url)
                else:
                    warning_message = format_html(
                        _("Organizations can't be edited until the "
                          "<a href='{}'>current bulk upload</a> "
                          "has finished."),
                        status_url
                    )
                    messages.warning(request, warning_message)
                    return view_fn(request, domain, *args, **kwargs)
            else:
                return view_fn(request, domain, *args, **kwargs)
        return new_fn
    return _outer


class BaseLocationView(BaseDomainView):
    section_name = gettext_lazy("Locations")

    @property
    def can_access_all_locations(self):
        return self.request.couch_user.has_permission(self.domain, 'access_all_locations')

    @property
    def section_url(self):
        return reverse(LocationsListView.urlname, args=[self.domain])

    @property
    def main_context(self):
        context = super(BaseLocationView, self).main_context
        context.update({
            'hierarchy': location_hierarchy_config(self.domain),
            'api_root': reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                             'resource_name': 'location_internal',
                                                             'api_name': 'v0.5'}),
        })
        return context


@location_safe
class LocationsListView(BaseLocationView):
    urlname = 'manage_locations'
    page_title = gettext_noop("Organization Structure")
    template_name = 'locations/manage/locations.html'

    @use_jquery_ui
    @method_decorator(check_pending_locations_import())
    @method_decorator(require_can_edit_or_view_locations)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseLocationView, self).dispatch(request, *args, **kwargs)

    @property
    def show_inactive(self):
        return json.loads(self.request.GET.get('show_inactive', 'false'))

    @property
    def page_context(self):
        has_location_types = len(self.domain_object.location_types) > 0
        bulk_download_url = reverse(FilteredLocationDownload.urlname, args=[self.domain])

        return {
            'bulk_download_url': bulk_download_url,
            'locations': self.get_visible_locations(),
            'show_inactive': self.show_inactive,
            'has_location_types': has_location_types,
            'can_edit_root': self.can_access_all_locations,
            'location_search_help': ExpandedMobileWorkerFilter.location_search_help,
            'user_is_domain_admin': self.request.couch_user.is_domain_admin(self.domain),
        }

    def get_visible_locations(self):
        def to_json(loc):
            return {
                'name': loc.name,
                'location_type': loc.location_type.name,
                'uuid': loc.location_id,
                'is_archived': loc.is_archived,
                'can_edit': True,
            }

        user = self.request.couch_user
        if self.can_access_all_locations:
            locs = filter_for_archived(
                SQLLocation.objects.filter(domain=self.domain, parent_id=None),
                self.show_inactive,
            )
            return list(map(to_json, locs))
        else:
            return [to_json(location) for location in user.get_sql_locations(self.domain)]


@location_safe
@method_decorator(require_can_edit_or_view_locations, name='dispatch')
class FilteredLocationDownload(BaseLocationView):
    urlname = 'filter_and_download_locations'
    page_title = gettext_noop('Filter and Download Locations')
    template_name = 'locations/filter_and_download.html'

    @property
    def page_context(self):
        return {
            'form': LocationFilterForm(self.request.GET, domain=self.domain, user=self.request.couch_user),
            'locations_count_url': reverse('locations_count', args=[self.domain])
        }


class LocationOptionsController(EmwfOptionsController):
    namespace_locations = False
    case_sharing_only = False

    @property
    def data_sources(self):
        return [
            (self.get_locations_size, self.get_locations),
        ]


@method_decorator(locations_access_required, name='dispatch')
class LocationsSearchView(EmwfOptionsView):

    @property
    @memoized
    def options_controller(self):
        return LocationOptionsController(self.request, self.domain, self.search)


class LocationFieldsView(CustomDataModelMixin, BaseLocationView):
    urlname = 'location_fields_view'
    field_type = 'LocationFields'
    entity_string = gettext_lazy("Location")
    template_name = "custom_data_fields/custom_data_fields.html"

    @method_decorator(locations_access_required)
    @method_decorator(domain_admin_required)
    @method_decorator(check_pending_locations_import())
    def dispatch(self, request, *args, **kwargs):
        return super(LocationFieldsView, self).dispatch(request, *args, **kwargs)


class LocationTypesView(BaseDomainView):
    urlname = 'location_types'
    page_title = gettext_noop("Organization Levels")
    template_name = 'locations/location_types.html'
    section_name = gettext_lazy("Locations")

    @property
    def section_url(self):
        return reverse(LocationsListView.urlname, args=[self.domain])

    @use_jquery_ui
    @method_decorator(can_edit_location_types)
    @method_decorator(require_can_edit_locations)
    @method_decorator(check_pending_locations_import())
    def dispatch(self, request, *args, **kwargs):
        return super(LocationTypesView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'location_types': self._location_types,
            'commtrack_enabled': self.domain_object.commtrack_enabled,
            'suggest_orphan_case_alerts_setting': self._suggest_orphan_case_alerts_setting,
            'project_settings_url': reverse('domain_settings_default', args=[self.domain])
        }

    @property
    def _suggest_orphan_case_alerts_setting(self):
        """Determine if the `orphan_case_alerts_warning` info banner should be shown. It should be shown when
        the setting is disabled and any organization level can own cases
        """
        if self.domain_object.orphan_case_alerts_warning:
            return False

        return any(filter(lambda location_type: location_type['shares_cases'], self._location_types))

    @cached_property
    def _location_types(self):
        return [{
            'pk': loc_type.pk,
            'name': loc_type.name,
            'parent_type': (loc_type.parent_type.pk
                            if loc_type.parent_type else None),
            'administrative': loc_type.administrative,
            'shares_cases': loc_type.shares_cases,
            'view_descendants': loc_type.view_descendants,
            'code': loc_type.code,
            'expand_from': loc_type.expand_from.pk if loc_type.expand_from else None,
            'expand_from_root': loc_type.expand_from_root,
            'expand_to': loc_type.expand_to_id if loc_type.expand_to_id else None,
            'include_without_expanding': (loc_type.include_without_expanding_id
                                          if loc_type.include_without_expanding_id else None),
            'include_only': list(loc_type.include_only.values_list('pk', flat=True)),
        } for loc_type in LocationType.objects.by_domain(self.domain)]

    @method_decorator(lock_locations)
    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))
        sql_loc_types = {}

        def _is_fake_pk(pk):
            return isinstance(pk, str) and pk.startswith("fake-pk-")

        def mk_loctype(name, parent_type, administrative,
                       shares_cases, view_descendants, pk, code, **kwargs):
            parent = sql_loc_types[parent_type] if parent_type else None

            loc_type = None
            if not _is_fake_pk(pk):
                try:
                    loc_type = LocationType.objects.get(domain=self.domain, pk=pk)
                except LocationType.DoesNotExist:
                    pass
            if loc_type is None:
                loc_type = LocationType(domain=self.domain)
            loc_type.name = name
            loc_type.administrative = administrative
            loc_type.parent_type = parent
            loc_type.shares_cases = shares_cases
            loc_type.view_descendants = view_descendants
            loc_type.code = unicode_slug(code)
            sql_loc_types[pk] = loc_type
            loc_type.save()

        def unique_name_and_code():
            current_location_types = LocationType.objects.by_domain(request.domain)
            for location_type in current_location_types:
                if location_type.pk in payload_loc_type_name_by_pk:
                    # to check if the name/code was swapped with another location by confirming if
                    # either name/code has changed but the current name is still present in the names/codes passed
                    if (
                        location_type.name != payload_loc_type_name_by_pk.get(location_type.pk)
                        and location_type.name in names
                    ) or (
                        location_type.code != payload_loc_type_code_by_pk.get(location_type.pk)
                        and location_type.code in codes
                    ):
                        return False
            return True

        loc_types = payload['loc_types']
        pks = []
        payload_loc_type_name_by_pk = {}
        payload_loc_type_code_by_pk = {}
        for loc_type in loc_types:
            for prop in ['name', 'parent_type', 'administrative',
                         'shares_cases', 'view_descendants', 'pk']:
                if prop not in loc_type:
                    raise LocationConsistencyError("Missing an organization level property!")
            pk = loc_type['pk']
            if not _is_fake_pk(pk):
                pks.append(loc_type['pk'])
            loc_type['name'] = loc_type['name'].strip()
            payload_loc_type_name_by_pk[loc_type['pk']] = loc_type['name']
            if loc_type.get('code'):
                payload_loc_type_code_by_pk[loc_type['pk']] = loc_type['code']
        names = list(payload_loc_type_name_by_pk.values())
        names_are_unique = len(names) == len(set(names))
        codes = list(payload_loc_type_code_by_pk.values())
        codes_are_unique = len(codes) == len(set(codes))
        if not names_are_unique or not codes_are_unique:
            raise LocationConsistencyError("'name' and 'code' are supposed to be unique")

        if not unique_name_and_code():
            messages.error(request, LocationConsistencyError(_(
                "Looks like you are assigning a location name/code to a different location "
                "in the same request. Please do this in two separate updates by using a "
                "temporary name to free up the name/code to be re-assigned."))
            )
            return self.get(request, *args, **kwargs)
        hierarchy = self.get_hierarchy(loc_types)

        if not self.remove_old_location_types(pks):
            return self.get(request, *args, **kwargs)

        for loc_type in hierarchy:
            # make all locations in order
            mk_loctype(**loc_type)

        for loc_type in hierarchy:
            # apply sync boundaries (expand_from, expand_to and include_without_expanding) after the
            # locations are all created since there are dependencies between them
            self._attach_sync_boundaries_to_location_type(loc_type, sql_loc_types)

        return HttpResponseRedirect(reverse(self.urlname, args=[self.domain]))

    @staticmethod
    def _attach_sync_boundaries_to_location_type(loc_type_data, loc_type_db):
        """Store the sync expansion boundaries along with the location type. i.e. where
        the user's locations start expanding from, and where they expand to

        """
        loc_type = loc_type_db[loc_type_data['pk']]
        expand_from_id = loc_type_data['expand_from']
        expand_to_id = loc_type_data['expand_to']
        include_without_expanding_id = loc_type_data['include_without_expanding']
        include_only_ids = loc_type_data['include_only']
        try:
            loc_type.expand_from = loc_type_db[expand_from_id] if expand_from_id else None
        except KeyError:        # expand_from location type was deleted
            loc_type.expand_from = None
        loc_type.expand_from_root = loc_type_data['expand_from_root']
        try:
            loc_type.expand_to = loc_type_db[expand_to_id] if expand_to_id else None
        except KeyError:        # expand_to location type was deleted
            loc_type.expand_to = None
        try:
            loc_type.include_without_expanding = (loc_type_db[include_without_expanding_id]
                                                  if include_without_expanding_id else None)
        except KeyError:        # include_without_expanding location type was deleted
            loc_type.include_without_expanding = None
        include_only = LocationTypesView._get_include_only(include_only_ids, loc_type_db)
        loc_type.include_only.set(include_only)
        loc_type.save()

    @staticmethod
    def _get_include_only(include_only_ids, loc_type_db):
        """The user specified that we include loc types `include_only_ids`, but
        we need to insert any parent location types"""
        loc_types_by_pk = {lt.pk: lt for lt in loc_type_db.values()}
        include_only = {}

        def insert_with_parents(pk):
            if pk not in include_only:
                loc_type = loc_types_by_pk[pk]
                include_only[pk] = loc_type
                if loc_type.parent_type_id:
                    insert_with_parents(loc_type.parent_type_id)

        # if these types were just created, the user-provided IDs were placeholders
        user_specified = [loc_type_db[lt_id].pk for lt_id in include_only_ids]
        for pk in user_specified:
            insert_with_parents(pk)
        return include_only

    def remove_old_location_types(self, pks):
        existing_pks = (LocationType.objects.filter(domain=self.domain)
                                            .values_list('pk', flat=True))
        to_delete = []
        for pk in existing_pks:
            if pk not in pks:
                if (SQLLocation.objects.filter(domain=self.domain,
                                               location_type=pk)
                                       .exists()):
                    msg = _("You cannot delete organization levels that have locations")
                    messages.warning(self.request, msg)
                    return False
                to_delete.append(pk)
        (LocationType.objects.filter(domain=self.domain, pk__in=to_delete)
                             .delete())
        return True

    # This is largely copy-pasted from the LocationTypeManager
    def get_hierarchy(self, loc_types):
        """
        Return loc types in order from parents to children
        """
        assert_no_cycles([
            (lt['pk'], lt['parent_type'])
            if lt['parent_type'] else
            (lt['pk'], ROOT_LOCATION_TYPE)
            for lt in loc_types
        ])

        lt_dict = {lt['pk']: lt for lt in loc_types}
        hierarchy = {}

        def insert_loc_type(loc_type):
            """
            Get parent location's hierarchy, insert loc_type into it,
            and return hierarchy below loc_type
            """
            name = loc_type['name']
            parent = lt_dict.get(loc_type['parent_type'], None)
            if not parent:
                lt_hierarchy = hierarchy
            else:
                lt_hierarchy = insert_loc_type(parent)
            if name not in lt_hierarchy:
                lt_hierarchy[name] = (loc_type, {})
            return lt_hierarchy[name][1]

        for loc_type in loc_types:
            insert_loc_type(loc_type)

        ordered_loc_types = []

        def step_through_graph(hierarchy):
            for name, (loc_type, children) in hierarchy.items():
                ordered_loc_types.append(loc_type)
                step_through_graph(children)

        step_through_graph(hierarchy)
        return ordered_loc_types


class BaseEditLocationView(BaseLocationView):
    template_name = 'locations/manage/location.html'
    creates_new_location = True
    form_tab = 'basic'

    @property
    def parent_pages(self):
        selected = self.location.location_id or self.location.parent_location_id
        breadcrumbs = [{
            'title': LocationsListView.page_title,
            'url': reverse(
                LocationsListView.urlname,
                args=[self.domain],
                params={"selected": selected} if selected else None,
            )
        }]
        if self.location.parent:
            sql_parent = self.location.parent
            for loc in sql_parent.get_ancestors(include_self=True):
                breadcrumbs.append({
                    'title': loc.name,
                    'url': reverse(
                        EditLocationView.urlname,
                        args=[self.domain, loc.location_id],
                    )
                })
        return breadcrumbs

    @property
    @memoized
    def location_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return LocationFormSet(
            self.location,
            self.request,
            bound_data=data,
            is_new=self.creates_new_location,
        )

    def form_valid(self):
        messages.success(self.request, _('Location saved!'))
        return HttpResponseRedirect(
            reverse(EditLocationView.urlname,
                    args=[self.domain,
                          self.location_form.location.location_id]),
        )

    def settings_form_post(self, request, *args, **kwargs):
        if self.location_form.is_valid():
            self.location_form.save()
            return self.form_valid()
        return self.get(request, *args, **kwargs)

    @property
    def consumption(self):
        return None

    @property
    @memoized
    def location(self):
        parent_id = self.request.GET.get('parent')
        parent = (get_object_or_404(SQLLocation, domain=self.domain,
                                    location_id=parent_id)
                  if parent_id else None)
        return SQLLocation(domain=self.domain, parent=parent)

    @method_decorator(lock_locations)
    def post(self, request, *args, **kwargs):
        return self.settings_form_post(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'form': self.location_form,
            'location': self.location,
            'consumption': self.consumption,
            'locations': load_locs_json(self.domain, self.location.parent_location_id,
                                        user=self.request.couch_user),
            'form_tab': self.form_tab,
            'creates_new_location': self.creates_new_location,
        }


@location_safe
class NewLocationView(BaseEditLocationView):
    urlname = 'create_location'
    page_title = gettext_noop("New Location")

    @use_multiselect
    @method_decorator(require_can_edit_locations)
    @method_decorator(check_pending_locations_import(redirect=True))
    def dispatch(self, request, *args, **kwargs):
        return super(NewLocationView, self).dispatch(request, *args, **kwargs)


@location_safe
@can_edit_location
def archive_location(request, domain, loc_id):
    loc = get_object_or_404(SQLLocation, domain=domain, location_id=loc_id)
    loc.archive()
    return json_response({
        'success': True,
        'message': _("Location '{location_name}' has successfully been {action}.").format(
            location_name=loc.name,
            action=_("archived"),
        )
    })


@require_http_methods(['DELETE'])
@can_edit_location
@lock_locations
@location_safe
def delete_location(request, domain, loc_id):
    loc = get_object_or_404(SQLLocation, domain=domain, location_id=loc_id)
    loc.full_delete()
    return json_response({
        'success': True,
        'message': _("Location '{location_name}' has successfully been {action}.").format(
            location_name=loc.name,
            action=_("deleted"),
        )
    })


@location_safe
def location_lineage(request, domain, loc_id):
    lineage = SQLLocation.objects.get_locations([loc_id])[0].lineage
    for ancestor_idx in range(len(lineage)):
        lineage[ancestor_idx] = SQLLocation.objects.get_locations([lineage[ancestor_idx]])[0].to_json()
    lineage.insert(0, SQLLocation.objects.get_locations([loc_id])[0].to_json())
    return json_response({
        'lineage': lineage
    })


@can_edit_location
@location_safe
def location_descendants_count(request, domain, loc_id):
    loc = get_object_or_404(SQLLocation, domain=domain, location_id=loc_id)
    count = loc.get_descendants(include_self=True).count()
    return json_response({
        'count': count
    })


@can_edit_location
@location_safe
def unarchive_location(request, domain, loc_id):
    loc = get_object_or_404(SQLLocation, domain=domain, location_id=loc_id)
    loc.unarchive()
    return json_response({
        'success': True,
        'message': _("Location '{location_name}' has successfully been {action}.").format(
            location_name=loc.name,
            action=_("unarchived"),
        )
    })


@location_safe
class EditLocationView(BaseEditLocationView):
    urlname = 'edit_location'
    page_title = gettext_noop("Edit Location")
    creates_new_location = False

    @use_multiselect
    @method_decorator(check_pending_locations_import(redirect=True))
    @method_decorator(can_edit_or_view_location)
    def dispatch(self, request, *args, **kwargs):
        return super(EditLocationView, self).dispatch(request, *args, **kwargs)

    @property
    def location_id(self):
        return self.kwargs['loc_id']

    @property
    @memoized
    def location(self):
        return get_object_or_404(SQLLocation, domain=self.domain,
                                 location_id=self.location_id)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.location_id])

    @property
    def consumption(self):
        consumptions = []
        for product in Product.by_domain(self.domain):
            consumption = get_default_monthly_consumption(
                self.domain,
                product._id,
                self.location.location_type_name,
                self.location.supply_point_id or None,
            )
            if consumption:
                consumptions.append((product.name, consumption))
        return consumptions

    @property
    @memoized
    def products_form(self):
        if (
            self.location.location_type.administrative
            or not toggles.PRODUCTS_PER_LOCATION.enabled(self.request.domain)
        ):
            return None

        form = MultipleSelectionForm(
            initial={'selected_ids': self.products_at_location},
            submit_label=_("Update Product List"),
            fieldset_title=_("Specify Products Per Location"),
            prefix="products",
        )
        form.fields['selected_ids'].choices = self.active_products
        form.fields['selected_ids'].label = _("Products at Location")
        return form

    @property
    @memoized
    def users_form(self):
        if not (self.can_edit_commcare_users or self.can_access_all_locations):
            return None
        form = UsersAtLocationForm(
            request=self.request,
            domain_object=self.domain_object,
            location=self.location,
            data=self.request.POST if self.request.method == "POST" else None,
        )
        return form

    @property
    def active_products(self):
        return [(p.product_id, p.name)
                for p in SQLProduct.objects.filter(domain=self.domain, is_archived=False).all()]

    @property
    def products_at_location(self):
        return [p.product_id for p in self.location.products.all()]

    @property
    def page_name(self):
        if self.request.is_view_only:
            name = _("View {name} <small>{type}</small>")
        else:
            name = _("Edit {name} <small>{type}</small>")
        return format_html(name, name=self.location.name, type=self.location.location_type_name)

    @property
    def can_edit_commcare_users(self):
        return self.request.couch_user.can_edit_commcare_users()

    @property
    def can_edit_users_in_location(self):
        return (self.request.couch_user.can_edit_users_in_locations()
                or self.request.couch_user.can_edit_commcare_users())

    @property
    def page_context(self):
        context = super(EditLocationView, self).page_context

        if self.request.is_view_only:
            make_form_readonly(self.location_form.location_form)
            make_form_readonly(self.location_form.custom_location_data.form)
            make_form_readonly(self.products_form)
            make_form_readonly(self.users_form)
        elif not self.can_edit_users_in_location:
            make_form_readonly(self.users_form)

        context.update({
            'products_per_location_form': self.products_form,
            'users_per_location_form': self.users_form,
            'can_edit_commcare_users': self.can_edit_commcare_users,
            'can_edit_users_in_location': self.can_edit_users_in_location,
        })
        return context

    def users_form_post(self, request, *args, **kwargs):
        if self.users_form and self.users_form.is_valid():
            self.users_form.save()
            return self.form_valid()
        else:
            self.request.method = "GET"
            self.form_tab = 'users'
            return self.get(request, *args, **kwargs)

    def products_form_post(self, request, *args, **kwargs):
        products = SQLProduct.objects.filter(
            product_id__in=request.POST.getlist('products-selected_ids', [])
        )
        self.location.products = products
        self.location.save()
        return self.form_valid()

    @method_decorator(lock_locations)
    def post(self, request, *args, **kwargs):
        if self.request.is_view_only:
            messages.error(request,
                           _("You do not have permission to edit locations."))
            return super(EditLocationView, self).get(request, *args, **kwargs)

        if self.request.POST['form_type'] == "location-users":
            if self.can_edit_users_in_location:
                return self.users_form_post(request, *args, **kwargs)
            else:
                messages.error(
                    request, _("You do not have permission to edit Mobile Workers.")
                )
                return super(EditLocationView, self).get(request, *args, **kwargs)

        if self.request.POST['form_type'] == "location-settings":
            return self.settings_form_post(request, *args, **kwargs)
        elif (self.request.POST['form_type'] == "location-products"
              and toggles.PRODUCTS_PER_LOCATION.enabled(request.domain)):
            return self.products_form_post(request, *args, **kwargs)
        else:
            raise Http404()


@location_safe
class LocationImportStatusView(BaseLocationView):
    urlname = 'location_import_status'
    page_title = gettext_noop('Organization Structure Import Status')
    template_name = 'hqwebapp/bootstrap3/soil_status_full.html'

    @method_decorator(require_can_edit_locations)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseLocationView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = super(LocationImportStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('location_importer_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Organization Structure Import Status"),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
        })
        return render(request, self.template_name, context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@location_safe
class LocationImportView(BaseLocationView):
    urlname = 'location_import'
    page_title = gettext_noop('Upload Organization Structure From Excel')
    template_name = 'locations/manage/import.html'

    @method_decorator(require_can_edit_locations)
    @method_decorator(check_pending_locations_import(redirect=True))
    def dispatch(self, request, *args, **kwargs):
        return super(LocationImportView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        def _get_manage_consumption():
            if self.domain_object.commtrack_settings:
                return self.domain_object.commtrack_settings.individual_consumption_defaults
            else:
                return False

        context = {
            'bulk_upload': {
                "download_url": reverse(
                    "location_export", args=(self.domain,)),
                "adjective": _("Organization Structure"),
                "plural_noun": _("Organization Structure"),
            },
            "manage_consumption": _get_manage_consumption(),
        }
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('bulk_upload_file')
        if not upload:
            messages.error(request, _('no file uploaded'))
            return self.get(request, *args, **kwargs)
        if not args:
            messages.error(request, _('no domain specified'))
            return self.get(request, *args, **kwargs)

        if not upload.name.endswith('.xlsx'):
            messages.error(request, _("Invalid file-format. Please upload a valid xlsx file."))
            return self.get(request, *args, **kwargs)

        try:
            get_workbook(upload)
        except WorkbookJSONError as e:
            messages.error(request, e)
            return self.get(request, *args, **kwargs)

        domain = args[0]

        ref = self._cache_file(request, domain, upload)
        if not isinstance(ref, LocationImportView.Ref):
            # ref is HTTP response: lock could not be acquired
            return ref
        file_ref = ref.value
        task = import_locations_async.delay(domain, file_ref.download_id, request.couch_user.user_id)
        file_ref.set_task(task)
        return HttpResponseRedirect(
            reverse(
                LocationImportStatusView.urlname,
                args=[domain, file_ref.download_id]
            )
        )

    @staticmethod
    @lock_locations
    def _cache_file(request, domain, upload):
        """Stash in soil for ten hours to make it easier to pass to celery

        :returns: `LocationImportView.Ref` object that can be identified
        with `isinstance(rval, LocationImportView.Ref)` or an HTTP
        response generated by `lock_locations` (and guaranteed not to be
        `LocationImportView.Ref`) if the lock could not be acquired.
        """
        TEN_HOURS = 10 * 60 * 60
        file_ref = expose_cached_download(
            upload.read(),
            expiry=TEN_HOURS,
            file_extension=file_extention_from_filename(upload.name),
        )
        # put the file_ref.download_id in cache to lookup from elsewhere
        cache.set(import_locations_task_key(domain), file_ref.download_id, TEN_HOURS)
        return LocationImportView.Ref(file_ref)

    class Ref(object):

        def __init__(self, value):
            self.value = value


@require_can_edit_locations
@location_safe
def location_importer_job_poll(request, domain, download_id):
    template = "locations/manage/partials/locations_upload_status.html"
    try:
        context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError()

    context.update({
        'on_complete_short': _('Import complete.'),
        'on_complete_long': _('Organization Structure importing has finished'),

    })
    return render(request, template, context)


@require_can_edit_or_view_locations
@location_safe
def location_export(request, domain):
    headers_only = request.GET.get('download_type', 'full') == 'empty'
    if not LocationType.objects.filter(domain=domain).exists():
        messages.error(request, _("You need to define organization levels before "
                                  "you can do a bulk import or export."))
        return HttpResponseRedirect(reverse(LocationsListView.urlname, args=[domain]))

    include_consumption = request.GET.get('include_consumption') == 'true'
    owner_id = request.couch_user.get_id
    download = DownloadBase()

    form = LocationFilterForm(request.GET, domain=domain, user=request.couch_user)

    if form.is_valid():
        location_filters = form.get_filters()
    else:
        return HttpResponseBadRequest('Location filters invalid')

    root_location_ids = location_filters.pop('location_ids')
    res = download_locations_async.delay(domain, download.download_id, include_consumption,
                                         headers_only, owner_id, root_location_ids, **location_filters)
    download.set_task(res)
    return redirect(DownloadLocationStatusView.urlname, domain, download.download_id)


@require_can_edit_or_view_locations
@location_safe
def location_download_job_poll(request, domain,
                               download_id,
                               template="hqwebapp/partials/shared_download_status.html"):
    try:
        context = get_download_context(download_id, 'Preparing download')
        context.update({'link_text': _('Download Organization Structure')})
    except TaskFailedError as e:
        return HttpResponseServerError(e.errors)
    return render(request, template, context)


@location_safe
class DownloadLocationStatusView(BaseLocationView):
    urlname = 'download_org_structure_status'
    page_title = gettext_noop('Download Organization Structure Status')

    @method_decorator(require_can_edit_or_view_locations)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseLocationView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = super(DownloadLocationStatusView, self).main_context
        next_url = reverse(FilteredLocationDownload.urlname, args=[self.domain])
        next_url_text = _("Go back to organization download")

        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('org_download_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Download Organization Structure Status"),
            'progress_text': _("Preparing organization structure download."),
            'error_text': _("There was an unexpected error! Please try again or report an issue."),
            'next_url': next_url,
            'next_url_text': next_url_text,
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


class DowngradeLocationsView(BaseDomainView):
    """
    This page takes the place of the location pages if a domain gets
    downgraded, but still has users assigned to locations.
    """
    template_name = 'locations/downgrade_locations.html'
    urlname = 'downgrade_locations'
    section_name = gettext_lazy("Project Settings")
    page_title = gettext_lazy("Project Access")

    def dispatch(self, *args, **kwargs):
        if not users_have_locations(self.domain):  # irrelevant, redirect
            redirect_url = reverse('users_default', args=[self.domain])
            return HttpResponseRedirect(redirect_url)
        return super(DowngradeLocationsView, self).dispatch(*args, **kwargs)

    @property
    def section_url(self):
        return reverse('settings_default', args=(self.domain, ))


@domain_admin_required
def unassign_users(request, domain):
    """
    Unassign all users from their locations.  This is for downgraded domains.
    """
    for user in get_users_assigned_to_locations(domain):
        if user.is_web_user():
            user.unset_location(domain)
        elif user.is_commcare_user():
            user.unset_location()

    messages.success(request,
                     _("All users have been unassigned from their locations"))
    fallback_url = reverse('users_default', args=[domain])
    return HttpResponseRedirect(request.POST.get('redirect', fallback_url))


@require_can_edit_or_view_locations
@location_safe
def count_locations(request, domain):
    form = LocationFilterForm(request.GET, domain=domain, user=request.couch_user)

    if form.is_valid():
        location_filters = form.get_filters()
    else:
        return HttpResponseBadRequest('Location filters invalid')

    if location_filters.pop('selected_location_only'):
        locations_count = 1
    else:
        root_location_ids = location_filters.pop('location_ids')

        locations_count = get_filtered_locations_count(
            domain,
            root_location_ids=root_location_ids,
            **location_filters
        )

    return JsonResponse({
        'count': locations_count
    })
