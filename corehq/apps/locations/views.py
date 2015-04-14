import json
import logging

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_POST

from couchdbkit import ResourceNotFound, MultipleResultsFound
from couchexport.models import Format
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_response
from soil.exceptions import TaskFailedError
from soil.util import expose_download, get_download_context

from corehq import toggles
from corehq.apps.commtrack.exceptions import MultipleSupplyPointException
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.commtrack.tasks import import_locations_async
from corehq.apps.commtrack.util import unicode_slug
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption
from corehq.apps.custom_data_fields import CustomDataModelMixin
from corehq.apps.domain.decorators import domain_admin_required, login_and_domain_required
from corehq.apps.facilities.models import FacilityRegistry
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.users.forms import MultipleSelectionForm
from custom.openlmis.tasks import bootstrap_domain_task

from .models import Location, LocationType, SQLLocation
from .forms import LocationForm
from .util import load_locs_json, location_hierarchy_config, dump_locations


@domain_admin_required
def default(request, domain):
    return HttpResponseRedirect(reverse(LocationsListView.urlname, args=[domain]))


class BaseLocationView(BaseCommTrackManageView):

    @property
    def main_context(self):
        context = super(BaseLocationView, self).main_context
        context.update({
            'hierarchy': location_hierarchy_config(self.domain),
            'api_root': reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                             'resource_name': 'location',
                                                             'api_name': 'v0.3'}),
        })
        return context


class LocationsListView(BaseLocationView):
    urlname = 'manage_locations'
    page_title = ugettext_noop("Locations")
    template_name = 'locations/manage/locations.html'

    @property
    def show_inactive(self):
        return json.loads(self.request.GET.get('show_inactive', 'false'))

    @property
    def page_context(self):
        selected_id = self.request.GET.get('selected')
        has_location_types = len(self.domain_object.location_types) > 0
        return {
            'selected_id': selected_id,
            'locations': load_locs_json(
                self.domain, selected_id, self.show_inactive
            ),
            'show_inactive': self.show_inactive,
            'has_location_types': has_location_types
        }


class LocationFieldsView(CustomDataModelMixin, BaseLocationView):
    urlname = 'location_fields_view'
    field_type = 'LocationFields'
    entity_string = _("Location")


class LocationTypesView(BaseCommTrackManageView):
    urlname = 'location_types'
    page_title = ugettext_noop("Location Types")
    template_name = 'locations/settings.html'

    @property
    def page_context(self):
        return {
            'settings': self.settings_context,
            'commtrack_enabled': self.domain_object.commtrack_enabled,
        }

    @property
    def settings_context(self):
        return {
            'loc_types': map(
                self._get_loctype_info,
                LocationType.objects.by_domain(self.domain)
            )
        }

    def _get_loctype_info(self, loctype):
        return {
            'pk': loctype.pk,
            'name': loctype.name,
            'code': loctype.code,
            'allowed_parents': [loctype.parent_type.name
                                if loctype.parent_type else None],
            'administrative': loctype.administrative,
            'shares_cases': loctype.shares_cases,
            'view_descendants': loctype.view_descendants
        }

    def post(self, request, *args, **kwargs):
        # This is really ugly, it needs a refactor.
        # There are some changes coming to this UI, so I'm just gonna wait
        # for that.  I intend to remove "code" from the UI altogether, and
        # use the actual location_type pk to reference it, not the name.
        payload = json.loads(request.POST.get('json'))
        sql_loc_types = {}

        def mk_loctype(name, code, allowed_parents, administrative,
                       shares_cases, view_descendants, pk):
            if allowed_parents and allowed_parents[0]:
                parent = sql_loc_types[allowed_parents[0]]
            else:
                parent = None

            cleaned_code = unicode_slug(code)
            if cleaned_code != code:
                err = _('Location type code "{code}" is invalid. No spaces or '
                        'special characters are allowed. It has been replaced '
                        'with "{new_code}".')
                messages.warning(request,
                                 err.format(code=code, new_code=cleaned_code))

            try:
                loc_type = LocationType.objects.get(domain=self.domain, pk=pk)
            except LocationType.DoesNotExist:
                loc_type = LocationType(domain=self.domain)
            loc_type.name = name
            loc_type.code = cleaned_code
            loc_type.administrative = administrative
            loc_type.parent_type = parent
            loc_type.shares_cases = shares_cases
            loc_type.view_descendants = view_descendants
            loc_type.save()
            sql_loc_types[name] = loc_type

        loc_types = payload['loc_types']
        pks = []
        for loc_type in loc_types:
            for prop in ['name', 'code', 'allowed_parents', 'administrative',
                         'shares_cases', 'view_descendants', 'pk']:
                assert prop in loc_type, "Missing a location type property!"
                assert len(loc_type['allowed_parents']) <= 1, \
                    "This location type has more than one parent. How?"
            pks.append(loc_type['pk'])

        hierarchy = self.get_hierarchy(loc_types)

        if not self.remove_old_location_types(pks):
            return self.get(request, *args, **kwargs)

        for loc_type in hierarchy:
            mk_loctype(**loc_type)

        return self.get(request, *args, **kwargs)

    def remove_old_location_types(self, pks):
        existing_pks = (LocationType.objects.filter(domain=self.domain)
                                            .values_list('pk', flat=True))
        to_delete = []
        for pk in existing_pks:
            if pk not in pks:
                if (SQLLocation.objects.filter(domain=self.domain,
                                               location_type=pk)
                                       .exists()):
                    msg = _("You cannot delete location types that have locations")
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
        lt_dict = {lt['name']: lt for lt in loc_types}

        # Make sure there are no cycles
        for loc_type in loc_types:
            visited = set()

            def step(lt):
                assert lt['name'] not in visited, \
                    "There's a loc type cycle, we need to prohibit that"
                visited.add(lt['name'])
                parents = lt['allowed_parents']
                if parents and parents[0]:
                    step(lt_dict.get(parents[0]))
            step(loc_type)

        hierarchy = {}

        def insert_loc_type(loc_type):
            """
            Get parent location's hierarchy, insert loc_type into it,
            and return hierarchy below loc_type
            """
            name = loc_type['name']
            parents = loc_type['allowed_parents']
            parent = lt_dict.get(parents[0], None) if parents else None
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


class NewLocationView(BaseLocationView):
    urlname = 'create_location'
    page_title = ugettext_noop("New Location")
    template_name = 'locations/manage/location.html'

    @property
    def parent_pages(self):
        return [{
            'title': LocationsListView.page_title,
            'url': reverse(LocationsListView.urlname, args=[self.domain]),
        }]

    @property
    def parent_id(self):
        return self.request.GET.get('parent')

    @property
    @memoized
    def location(self):
        return Location(domain=self.domain, parent=self.parent_id)

    @property
    def consumption(self):
        return None

    @property
    @memoized
    def location_form(self):
        if self.request.method == 'POST':
            return LocationForm(self.location, self.request.POST, is_new=True)
        return LocationForm(self.location, is_new=True)

    @property
    def page_context(self):
        try:
            consumption = self.consumption
        except MultipleSupplyPointException:
            consumption = []
            logging.error("Invalid setup: Multiple supply point cases found for the location",
                          exc_info=True, extra={'request': self.request})
            messages.error(self.request, _(
                "There was a problem with the setup for your project. " +
                "Please contact support at commcarehq-support@dimagi.com."
            ))
        return {
            'form': self.location_form,
            'location': self.location,
            'consumption': consumption,
            'locations': load_locs_json(self.domain, self.parent_id),
        }

    def form_valid(self):
        messages.success(self.request, _('Location saved!'))
        return HttpResponseRedirect(
            reverse(EditLocationView.urlname,
                    args=[self.domain, self.location_form.location._id]),
        )

    def settings_form_post(self, request, *args, **kwargs):
        if self.location_form.is_valid():
            self.location_form.save()
            return self.form_valid()
        return self.get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.settings_form_post(request, *args, **kwargs)


@domain_admin_required
def archive_location(request, domain, loc_id):
    loc = Location.get(loc_id)
    if loc.domain != domain:
        raise Http404()
    loc.archive()
    return json_response({
        'success': True,
        'message': _("Location '{location_name}' has successfully been {action}.").format(
            location_name=loc.name,
            action="archived",
        )
    })


@domain_admin_required
def unarchive_location(request, domain, loc_id):
    # hack for circumventing cache
    # which was found to be out of date, at least in one case
    # http://manage.dimagi.com/default.asp?161454
    # todo: find the deeper reason for invalid cache
    loc = Location.get(loc_id, db=Location.get_db())
    if loc.domain != domain:
        raise Http404()
    loc.unarchive()
    return json_response({
        'success': True,
        'message': _("Location '{location_name}' has successfully been {action}.").format(
            location_name=loc.name,
            action="unarchived",
        )
    })


class EditLocationView(NewLocationView):
    urlname = 'edit_location'
    page_title = ugettext_noop("Edit Location")

    @property
    def location_id(self):
        return self.kwargs['loc_id']

    @property
    @memoized
    def location(self):
        try:
            location = Location.get(self.location_id)
            if location.domain != self.domain:
                raise Http404()
        except ResourceNotFound:
            raise Http404()
        else:
            return location

    @property
    @memoized
    def sql_location(self):
        return self.location.sql_location

    @property
    @memoized
    def supply_point(self):
        try:
            return SupplyPointCase.get_by_location(self.location)
        except MultipleResultsFound:
            raise MultipleSupplyPointException

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.location_id])

    @property
    @memoized
    def location_form(self):
        if self.request.method == 'POST':
            return LocationForm(self.location, self.request.POST)
        return LocationForm(self.location)

    @property
    def consumption(self):
        consumptions = []
        for product in Product.by_domain(self.domain):
            consumption = get_default_monthly_consumption(
                self.domain,
                product._id,
                self.location.location_type,
                # FIXME accessing this value from the sql location
                # would be faster
                self.supply_point._id if self.supply_point else None,
            )
            if consumption:
                consumptions.append((product.name, consumption))
        return consumptions

    @property
    def products_form(self):
        if (
            self.location.location_type_object.administrative or
            not toggles.PRODUCTS_PER_LOCATION.enabled(self.request.domain)
        ):
            return None

        form = MultipleSelectionForm(
            initial={'selected_ids': self.products_at_location},
            submit_label=_("Update Product List")
        )
        form.fields['selected_ids'].choices = self.all_products
        return form

    @property
    def all_products(self):
        return [(p.product_id, p.name)
                for p in SQLProduct.by_domain(self.domain)]

    @property
    def products_at_location(self):
        return [p.product_id for p in self.sql_location.products.all()]

    @property
    def page_name(self):
        return mark_safe(_("Edit {name} <small>{type}</small>").format(
            name=self.location.name, type=self.location.location_type
        ))

    @property
    def page_context(self):
        context = super(EditLocationView, self).page_context
        context.update({
            'products_per_location_form': self.products_form,
        })
        return context

    def products_form_post(self, request, *args, **kwargs):
        products = SQLProduct.objects.filter(
            product_id__in=request.POST.getlist('selected_ids', [])
        )
        self.sql_location.products = products
        self.sql_location.save()
        return self.form_valid()

    def post(self, request, *args, **kwargs):
        if self.request.POST['form_type'] == "location-settings":
            return self.settings_form_post(request, *args, **kwargs)
        elif (self.request.POST['form_type'] == "location-products"
              and toggles.PRODUCTS_PER_LOCATION.enabled(request.domain)):
            return self.products_form_post(request, *args, **kwargs)
        else:
            raise Http404()


class BaseSyncView(BaseLocationView):
    source = ""
    sync_urlname = None

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


class FacilitySyncView(BaseSyncView):
    urlname = 'sync_facilities'
    sync_urlname = 'sync_openlmis'
    page_title = ugettext_noop("OpenLMIS")
    template_name = 'locations/facility_sync.html'
    source = 'openlmis'


class LocationImportStatusView(BaseLocationView):
    urlname = 'location_import_status'
    page_title = ugettext_noop('Location Import Status')
    template_name = 'hqwebapp/soil_status_full.html'

    def get(self, request, *args, **kwargs):
        context = super(LocationImportStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('location_importer_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Location Import Status"),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
        })
        return render(request, self.template_name, context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


class LocationImportView(BaseLocationView):
    urlname = 'location_import'
    page_title = ugettext_noop('Upload Locations from Excel')
    template_name = 'locations/manage/import.html'

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
                "adjective": _("location"),
                "plural_noun": _("locations"),
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

        domain = args[0]

        # stash this in soil to make it easier to pass to celery
        file_ref = expose_download(upload.read(),
                                   expiry=1*60*60)
        task = import_locations_async.delay(
            domain,
            file_ref.download_id,
        )
        file_ref.set_task(task)
        return HttpResponseRedirect(
            reverse(
                LocationImportStatusView.urlname,
                args=[domain, file_ref.download_id]
            )
        )


@login_and_domain_required
def location_importer_job_poll(request, domain, download_id, template="hqwebapp/partials/download_status.html"):
    try:
        context = get_download_context(download_id, check_state=True)
    except TaskFailedError:
        return HttpResponseServerError()

    context.update({
        'on_complete_short': _('Import complete.'),
        'on_complete_long': _('Location importing has finished'),

    })
    return render(request, template, context)


@login_and_domain_required
def location_export(request, domain):
    include_consumption = request.GET.get('include_consumption') == 'true'
    response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename="locations.xlsx"'
    dump_locations(response, domain, include_consumption)
    return response


@domain_admin_required
@require_POST
def sync_facilities(request, domain):
    # TODO this is believed to be obsolete and should
    # likely be removed, just need to make sure it isn't
    # magically used by ils/ews first..
    # create Facility Registry and Facility LocationTypes if they don't exist
    facility_registry, is_new = LocationType.objects.get_or_create(
        domain=domain,
        name='Facility Registry',
    )
    if is_new:
        LocationType.objects.get_or_create(
            domain=domain,
            name='Facility',
            defaults={
                'parent_type': facility_registry,
            },
        )

    registry_locs = {
        l.external_id: l
        for l in Location.filter_by_type(domain, 'Facility Registry')
    }

    # sync each registry and add/update Locations for each Facility
    for registry in FacilityRegistry.by_domain(domain):
        registry.sync_with_remote()

        try:
            registry_loc = registry_locs[registry.url]
        except KeyError:
            registry_loc = Location(
                domain=domain, location_type='Facility Registry',
                external_id=registry.url)
        registry_loc.name = registry.name
        registry_loc.save()
        registry_loc._seen = True

        facility_locs = {
            l.external_id: l
            for l in Location.filter_by_type(domain, 'Facility', registry_loc)
        }

        for facility in registry.get_facilities():
            uuid = facility.data['uuid']
            try:
                facility_loc = facility_locs[uuid]
            except KeyError:
                facility_loc = Location(
                    domain=domain, location_type='Facility', external_id=uuid,
                    parent=registry_loc)
            facility_loc.name = facility.data.get('name', 'Unnamed Facility')
            facility_loc.save()
            facility_loc._seen = True

        for id, f in facility_locs.iteritems():
            if not hasattr(f, '_seen'):
                f.delete()

    for id, r in registry_locs.iteritems():
        if not hasattr(r, '_seen'):
            r.delete()

    return HttpResponse('OK')


@domain_admin_required
@require_POST
def sync_openlmis(request, domain):
    # todo: error handling, if we care.
    bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')
