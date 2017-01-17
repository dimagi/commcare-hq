import json
import logging

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.http.response import HttpResponseServerError
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from django.views.decorators.http import require_http_methods

from couchdbkit import ResourceNotFound, BulkSaveError
from corehq.apps.style.decorators import (
    use_jquery_ui,
    use_multiselect,
)
from corehq.util.files import file_extention_from_filename
from couchexport.models import Format
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_response
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context

from corehq import toggles
from corehq.apps.commtrack.tasks import import_locations_async, location_lock_key, LOCK_LOCATIONS_TIMEOUT
from corehq.apps.commtrack.util import unicode_slug
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.custom_data_fields import CustomDataModelMixin
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.forms import MultipleSelectionForm
from corehq.apps.locations.permissions import location_safe
from corehq.util import reverse
from dimagi.utils.couch import release_lock
from dimagi.utils.couch.cache.cache_core import get_redis_client

from .analytics import users_have_locations
from .const import ROOT_LOCATION_TYPE
from .dbaccessors import get_users_assigned_to_locations
from .exceptions import LocationConsistencyError
from .permissions import (
    locations_access_required,
    is_locations_admin,
    can_edit_location,
    can_edit_location_types,
    user_can_edit_any_location,
    can_edit_any_location,
)
from .models import LocationType, SQLLocation, filter_for_archived
from .forms import LocationForm, UsersAtLocationForm
from .tree_utils import assert_no_cycles
from .util import load_locs_json, location_hierarchy_config, dump_locations


logger = logging.getLogger(__name__)


@locations_access_required
def default(request, domain):
    return HttpResponseRedirect(reverse(LocationsListView.urlname, args=[domain]))


def lock_locations(func):
    # Decorate a post/delete method of a view to ensure concurrent locations edits don't happen.
    def func_wrapper(request, *args, **kwargs):
        key = location_lock_key(request.domain)
        client = get_redis_client()
        lock = client.lock(key, LOCK_LOCATIONS_TIMEOUT)
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
                    messages.warning(request, mark_safe(
                        _("Organizations can't be edited until "
                          "<a href='{}''>current bulk upload</a> "
                          "has finished.").format(status_url)
                    ))
                    return view_fn(request, domain, *args, **kwargs)
            else:
                return view_fn(request, domain, *args, **kwargs)
        return new_fn
    return _outer


class BaseLocationView(BaseDomainView):
    section_name = ugettext_lazy("Locations")

    @method_decorator(locations_access_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseLocationView, self).dispatch(request, *args, **kwargs)

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
    page_title = ugettext_noop("Organization Structure")
    template_name = 'locations/manage/locations.html'

    @use_jquery_ui
    @method_decorator(require_can_edit_commcare_users)
    @method_decorator(check_pending_locations_import())
    def dispatch(self, request, *args, **kwargs):
        return super(LocationsListView, self).dispatch(request, *args, **kwargs)

    @property
    def show_inactive(self):
        return json.loads(self.request.GET.get('show_inactive', 'false'))

    @property
    def can_edit_root(self):
        # once permissions are unified, this need only be can_access_all_locations
        loc_restricted = self.request.project.location_restriction_for_users
        return self.can_access_all_locations and (
            not loc_restricted
            or (loc_restricted and not self.request.couch_user.get_sql_location(self.domain))
        )

    @property
    def page_context(self):
        has_location_types = len(self.domain_object.location_types) > 0
        return {
            'locations': self.get_visible_locations(),
            'show_inactive': self.show_inactive,
            'has_location_types': has_location_types,
            'can_edit_root': self.can_edit_root,
            'can_edit_any_location': user_can_edit_any_location(self.request.couch_user, self.request.project),
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
            return map(to_json, locs)
        else:
            return [to_json(user.get_sql_location(self.domain))]


class LocationFieldsView(CustomDataModelMixin, BaseLocationView):
    urlname = 'location_fields_view'
    field_type = 'LocationFields'
    entity_string = ugettext_lazy("Location")
    template_name = "custom_data_fields/custom_data_fields.html"

    @method_decorator(is_locations_admin)
    @method_decorator(check_pending_locations_import())
    def dispatch(self, request, *args, **kwargs):
        return super(LocationFieldsView, self).dispatch(request, *args, **kwargs)


class LocationTypesView(BaseLocationView):
    urlname = 'location_types'
    page_title = ugettext_noop("Organization Levels")
    template_name = 'locations/location_types.html'

    @method_decorator(can_edit_location_types)
    @use_jquery_ui
    @method_decorator(check_pending_locations_import())
    def dispatch(self, request, *args, **kwargs):
        return super(LocationTypesView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'location_types': self._get_loc_types(),
            'commtrack_enabled': self.domain_object.commtrack_enabled,
        }

    def _get_loc_types(self):
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
        } for loc_type in LocationType.objects.by_domain(self.domain)]

    @method_decorator(lock_locations)
    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))
        sql_loc_types = {}

        def _is_fake_pk(pk):
            return isinstance(pk, basestring) and pk.startswith("fake-pk-")

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

        loc_types = payload['loc_types']
        pks = []
        for loc_type in loc_types:
            for prop in ['name', 'parent_type', 'administrative',
                         'shares_cases', 'view_descendants', 'pk']:
                if prop not in loc_type:
                    raise LocationConsistencyError("Missing an organization level property!")
            pk = loc_type['pk']
            if not _is_fake_pk(pk):
                pks.append(loc_type['pk'])

        names = [lt['name'] for lt in loc_types]
        names_are_unique = len(names) == len(set(names))
        codes = [lt['code'] for lt in loc_types if lt['code']]
        codes_are_unique = len(codes) == len(set(codes))
        if not names_are_unique or not codes_are_unique:
            raise LocationConsistencyError("'name' and 'code' are supposed to be unique")

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
        loc_type.save()

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


@location_safe
class NewLocationView(BaseLocationView):
    urlname = 'create_location'
    page_title = ugettext_noop("New Location")
    template_name = 'locations/manage/location.html'
    creates_new_location = True
    form_tab = 'basic'

    @use_multiselect
    @method_decorator(check_pending_locations_import(redirect=True))
    def dispatch(self, request, *args, **kwargs):
        return super(NewLocationView, self).dispatch(request, *args, **kwargs)

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
    def location(self):
        parent_id = self.request.GET.get('parent')
        parent = (get_object_or_404(SQLLocation, domain=self.domain, location_id=parent_id)
                  if parent_id else None)
        return SQLLocation(domain=self.domain, parent=parent)

    @property
    def consumption(self):
        return None

    @property
    @memoized
    def location_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return LocationForm(
            self.location,
            bound_data=data,
            user=self.request.couch_user,
            is_new=self.creates_new_location,
        )

    @property
    def page_context(self):
        return {
            'form': self.location_form,
            'location': self.location,
            'consumption': self.consumption,
            'locations': load_locs_json(self.domain, self.location.parent_location_id,
                                        user=self.request.couch_user),
            'form_tab': self.form_tab,
        }

    def form_valid(self):
        messages.success(self.request, _('Location saved!'))
        return HttpResponseRedirect(
            reverse(EditLocationView.urlname,
                    args=[self.domain, self.location_form.location.location_id]),
        )

    def settings_form_post(self, request, *args, **kwargs):
        if self.location_form.is_valid():
            self.location_form.save()
            return self.form_valid()
        return self.get(request, *args, **kwargs)

    @method_decorator(lock_locations)
    def post(self, request, *args, **kwargs):
        return self.settings_form_post(request, *args, **kwargs)


@location_safe
@can_edit_location
def archive_location(request, domain, loc_id):
    try:
        loc = SQLLocation.objects.get(domain=domain, location_id=loc_id)
    except SQLLocation.DoesNotExist:
        raise Http404()
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
    try:
        loc = SQLLocation.objects.get(domain=domain, location_id=loc_id)
    except SQLLocation.DoesNotExist:
        raise Http404()
    try:
        loc.full_delete()
    except (ResourceNotFound, BulkSaveError):
        # Sometimes the couch and sql locations go out of sync and we can end up
        # in a state where the couch doc is deleted and the sql doc still exists.
        # delete the sql locations anyway
        loc.sql_full_delete()
        logger.error(
            'Location with ID [{}] in domain [{}] was missing its couch doc '
            'upon deletion. If this is recurring it might be worth checking '
            'out any couch to postrgres issues.'.format(loc_id, domain)
        )
    return json_response({
        'success': True,
        'message': _("Location '{location_name}' has successfully been {action}.").format(
            location_name=loc.name,
            action=_("deleted"),
        )
    })


def location_descendants_count(request, domain, loc_id):
    location = SQLLocation.objects.get(location_id=loc_id)
    if location.domain != domain:
        raise Http404()
    count = len(location.get_descendants(include_self=True))
    return json_response({
        'count': count
    })


@can_edit_location
@location_safe
def unarchive_location(request, domain, loc_id):
    try:
        loc = SQLLocation.objects.get(domain=domain, location_id=loc_id)
    except SQLLocation.DoesNotExist:
        raise Http404()
    loc.unarchive()
    return json_response({
        'success': True,
        'message': _("Location '{location_name}' has successfully been {action}.").format(
            location_name=loc.name,
            action=_("unarchived"),
        )
    })


@location_safe
class EditLocationView(NewLocationView):
    urlname = 'edit_location'
    page_title = ugettext_noop("Edit Location")
    creates_new_location = False

    @method_decorator(can_edit_location)
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
    @memoized
    def sql_location(self):
        try:
            location = SQLLocation.objects.get(location_id=self.location_id)
            if location.domain != self.domain:
                raise Http404()
        except ResourceNotFound:
            raise Http404()
        else:
            return location

    @property
    @memoized
    def supply_point(self):
        return self.location.linked_supply_point()

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
                # FIXME accessing this value from the sql location
                # would be faster
                self.supply_point.case_id if self.supply_point else None,
            )
            if consumption:
                consumptions.append((product.name, consumption))
        return consumptions

    @property
    @memoized
    def products_form(self):
        if (
            self.location.location_type_object.administrative or
            not toggles.PRODUCTS_PER_LOCATION.enabled(self.request.domain)
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
        if not self.can_access_all_locations:
            return None
        form = UsersAtLocationForm(
            domain_object=self.domain_object,
            location=self.location,
            data=self.request.POST if self.request.method == "POST" else None,
            submit_label=_("Update Users at this Location"),
            fieldset_title=_("Specify Workers at this Location"),
            prefix="users",
        )
        return form

    @property
    def active_products(self):
        return [(p.product_id, p.name)
                for p in SQLProduct.objects.filter(domain=self.domain, is_archived=False).all()]

    @property
    def products_at_location(self):
        return [p.product_id for p in self.sql_location.products.all()]

    @property
    def page_name(self):
        return mark_safe(_("Edit {name} <small>{type}</small>").format(
            name=self.location.name, type=self.location.location_type_name
        ))

    @property
    def page_context(self):
        context = super(EditLocationView, self).page_context
        context.update({
            'products_per_location_form': self.products_form,
            'users_per_location_form': self.users_form,
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
        self.sql_location.products = products
        self.sql_location.save()
        return self.form_valid()

    @method_decorator(lock_locations)
    def post(self, request, *args, **kwargs):
        if self.request.POST['form_type'] == "location-settings":
            return self.settings_form_post(request, *args, **kwargs)
        elif self.request.POST['form_type'] == "location-users":
            return self.users_form_post(request, *args, **kwargs)
        elif (self.request.POST['form_type'] == "location-products"
              and toggles.PRODUCTS_PER_LOCATION.enabled(request.domain)):
            return self.products_form_post(request, *args, **kwargs)
        else:
            raise Http404()


class BaseSyncView(BaseLocationView):
    source = ""
    sync_urlname = None
    section_name = ugettext_lazy("Project Settings")

    @property
    def page_context(self):
        return {
            'settings': self.settings_context,
            'source': self.source,
            'sync_url': self.sync_urlname
        }

    @property
    def settings_context(self):
        key = "%s_config" % self.source
        if hasattr(self.domain_object.commtrack_settings, key):
            return {
                "source_config": getattr(self.domain_object.commtrack_settings, key)._doc,
            }
        else:
            return {}

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))

        #TODO add server-side input validation here (currently validated on client)
        key = "%s_config" % self.source
        if "source_config" in payload:
            for item in payload['source_config']:
                if hasattr(self.domain_object.commtrack_settings, key):
                    setattr(
                        getattr(self.domain_object.commtrack_settings, key),
                        item,
                        payload['source_config'][item]
                    )

        self.domain_object.commtrack_settings.save()

        return self.get(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse('settings_default', args=(self.domain,))


class LocationImportStatusView(BaseLocationView):
    urlname = 'location_import_status'
    page_title = ugettext_noop('Organization Structure Import Status')
    template_name = 'style/soil_status_full.html'

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


class LocationImportView(BaseLocationView):
    urlname = 'location_import'
    page_title = ugettext_noop('Upload Organization Structure From Excel')
    template_name = 'locations/manage/import.html'

    @method_decorator(can_edit_any_location)
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

    @method_decorator(lock_locations)
    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('bulk_upload_file')
        if not upload:
            messages.error(request, _('no file uploaded'))
            return self.get(request, *args, **kwargs)
        if not args:
            messages.error(request, _('no domain specified'))
            return self.get(request, *args, **kwargs)
        if upload.content_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            messages.error(request, _("Invalid file-format. Please upload a valid xlsx file."))
            return self.get(request, *args, **kwargs)

        domain = args[0]

        # stash this in soil to make it easier to pass to celery
        ONE_HOUR = 1*60*60
        file_ref = expose_cached_download(
            upload.read(),
            expiry=ONE_HOUR,
            file_extension=file_extention_from_filename(upload.name),
        )
        task = import_locations_async.delay(
            domain,
            file_ref.download_id,
        )
        # put the file_ref.download_id in cache to lookup from elsewhere
        cache.set(import_locations_task_key(domain), file_ref.download_id, ONE_HOUR)
        file_ref.set_task(task)
        return HttpResponseRedirect(
            reverse(
                LocationImportStatusView.urlname,
                args=[domain, file_ref.download_id]
            )
        )


@locations_access_required
def location_importer_job_poll(request, domain, download_id,
                               template="style/partials/download_status.html"):
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


@locations_access_required
def location_export(request, domain):
    if not LocationType.objects.filter(domain=domain).exists():
        messages.error(request, _("You need to define organization levels before "
                                  "you can do a bulk import or export."))
        return HttpResponseRedirect(reverse(LocationsListView.urlname, args=[domain]))
    include_consumption = request.GET.get('include_consumption') == 'true'
    response = HttpResponse(content_type=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename="{}_locations.xlsx"'.format(domain)
    dump_locations(response, domain, include_consumption=include_consumption)
    return response


@locations_access_required
@location_safe
def child_locations_for_select2(request, domain):
    id = request.GET.get('id')
    ids = request.GET.get('ids')
    query = request.GET.get('name', '').lower()
    user = request.couch_user

    base_queryset = SQLLocation.objects.accessible_to_user(domain, user)

    def loc_to_payload(loc):
        return {'id': loc.location_id, 'name': loc.display_name}

    if id:
        try:
            loc = base_queryset.get(location_id=id)
            if loc.domain != domain:
                raise SQLLocation.DoesNotExist()
        except SQLLocation.DoesNotExist:
            return json_response(
                {'message': 'no location with id %s found' % id},
                status_code=404,
            )
        else:
            return json_response(loc_to_payload(loc))
    elif ids:
        from corehq.apps.locations.util import get_locations_from_ids
        ids = json.loads(ids)
        try:
            locations = get_locations_from_ids(ids, domain, base_queryset=base_queryset)
        except SQLLocation.DoesNotExist:
            return json_response(
                {'message': 'one or more locations not found'},
                status_code=404,
            )
        return json_response([loc_to_payload(loc) for loc in locations])
    else:
        locs = []
        user_loc = user.get_sql_location(domain)

        if user_can_edit_any_location(user, request.project):
            locs = base_queryset.filter(domain=domain, is_archived=False)
        elif user_loc:
            locs = user_loc.get_descendants(include_self=True)

        if locs != [] and query:
            locs = locs.filter(name__icontains=query)

        return json_response(map(loc_to_payload, locs[:10]))


class DowngradeLocationsView(BaseDomainView):
    """
    This page takes the place of the location pages if a domain gets
    downgraded, but still has users assigned to locations.
    """
    template_name = 'locations/downgrade_locations.html'
    urlname = 'downgrade_locations'
    section_name = ugettext_lazy("Project Settings")
    page_title = ugettext_lazy("Project Access")

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
