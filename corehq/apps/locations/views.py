import copy
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from corehq.apps.commtrack.views import BaseCommTrackManageView

from corehq.apps.domain.decorators import domain_admin_required, login_and_domain_required
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.models import Location
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.util import load_locs_json, location_hierarchy_config, dump_locations
from corehq.apps.commtrack.models import LocationType, Product, SupplyPointCase
from corehq.apps.commtrack.util import unicode_slug
from corehq.apps.facilities.models import FacilityRegistry
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.contrib import messages
from couchdbkit import ResourceNotFound
import urllib
import json

from django.utils.translation import ugettext as _, ugettext_noop
from dimagi.utils.decorators.memoized import memoized
from custom.openlmis.tasks import bootstrap_domain_task
from custom.ilsgateway.tasks import bootstrap_domain_task as ils_bootstrap_domain_task
from soil.util import expose_download, get_download_context
from corehq.apps.commtrack.tasks import import_locations_async
from couchexport.models import Format
from corehq.apps.consumption.shortcuts import get_default_monthly_consumption


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
    def page_context(self):
        selected_id = self.request.GET.get('selected')
        return {
            'selected_id': selected_id,
            'locations': load_locs_json(self.domain, selected_id),
        }


class LocationSettingsView(BaseCommTrackManageView):
    urlname = 'location_settings'
    page_title = ugettext_noop("Location Types")
    template_name = 'locations/settings.html'

    @property
    def page_context(self):
        return {
            'settings': self.settings_context,
        }

    @property
    def settings_context(self):
        return {
            'loc_types': [self._get_loctype_info(l) for l in self.domain_object.commtrack_settings.location_types],
        }

    def _get_loctype_info(self, loctype):
        return {
            'name': loctype.name,
            'code': loctype.code,
            'allowed_parents': [p or None for p in loctype.allowed_parents],
            'administrative': loctype.administrative,
        }

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))

        def mk_loctype(loctype):
            loctype['allowed_parents'] = [p or '' for p in loctype['allowed_parents']]
            cleaned_code = unicode_slug(loctype['code'])
            if cleaned_code != loctype['code']:
                err = _(
                    'Location type code "{code}" is invalid. No spaces or special characters are allowed. '
                    'It has been replaced with "{new_code}".'
                )
                messages.warning(request, err.format(code=loctype['code'], new_code=cleaned_code))
                loctype['code'] = cleaned_code
            return LocationType(**loctype)

        #TODO add server-side input validation here (currently validated on client)

        self.domain_object.commtrack_settings.location_types = [mk_loctype(l) for l in payload['loc_types']]

        self.domain_object.commtrack_settings.save()

        return self.get(request, *args, **kwargs)


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
    def metadata(self):
        return copy.copy(dict(self.location.metadata))

    @property
    @memoized
    def location_form(self):
        if self.request.method == 'POST':
            return LocationForm(self.location, self.request.POST)
        return LocationForm(self.location)

    @property
    def page_context(self):
        return {
            'form': self.location_form,
            'location': self.location,
            'consumption': self.consumption,
            'metadata': self.metadata
        }

    def post(self, request, *args, **kwargs):
        if self.location_form.is_valid():
            self.location_form.save()
            messages.success(request, _('Location saved!'))
            return HttpResponseRedirect('%s?%s' % (
                reverse(LocationsListView.urlname, args=[self.domain]),
                urllib.urlencode({'selected': self.location_form.location._id})
            ))
        return self.get(request, *args, **kwargs)


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
            return Location.get(self.location_id)
        except ResourceNotFound:
            raise Http404()

    @property
    @memoized
    def supply_point(self):
        return SupplyPointCase.get_by_location(self.location)

    @property
    def consumption(self):
        consumptions = []
        for product in Product.by_domain(self.domain):
            consumption = get_default_monthly_consumption(
                self.domain,
                product._id,
                self.location.location_type,
                self.supply_point._id if self.supply_point else None,
            )
            if consumption:
                consumptions.append((product.name, consumption))
        return consumptions

    @property
    def page_name(self):
        return mark_safe(_("Edit {name} <small>{type}</small>").format(
            name=self.location.name, type=self.location.location_type
        ))

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.location_id])


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

class ILSFacilitySyncView(BaseSyncView):
    urlname = 'sync_facilities_ils'
    sync_urlname = 'sync_ilsgateway'
    page_title = ugettext_noop("ILSGateway")
    template_name = 'locations/facility_sync.html'
    source = 'ilsgateway'



class EditLocationHierarchy(BaseLocationView):
    urlname = 'location_hierarchy'
    page_title = ugettext_noop("Location Hierarchy")
    template_name = 'locations/location_hierarchy.html'


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
        context = {
            'bulk_upload': {
                "download_url": reverse(
                    "location_export", args=(self.domain,)),
                "adjective": _("location"),
                "plural_noun": _("locations"),
            },
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
    context = get_download_context(download_id, check_state=True)
    context.update({
        'on_complete_short': _('Import complete.'),
        'on_complete_long': _('Location importing has finished'),

    })
    return render(request, template, context)


def location_export(request, domain):
    response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename="locations.xlsx"'
    dump_locations(response, domain)
    return response


@domain_admin_required # TODO: will probably want less restrictive permission
def location_edit(request, domain, loc_id=None):
    parent_id = request.GET.get('parent')

    if loc_id:
        try:
            location = Location.get(loc_id)
        except ResourceNotFound:
            raise Http404()
    else:
        location = Location(domain=domain, parent=parent_id)

    if request.method == "POST":
        form = LocationForm(location, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Location saved!')
            return HttpResponseRedirect('%s?%s' % (
                    reverse('manage_locations', kwargs={'domain': domain}),
                    urllib.urlencode({'selected': form.location._id})
                ))
    else:
        form = LocationForm(location)

    context = {
        'domain': domain,
        'api_root': reverse('api_dispatch_list', kwargs={'domain': domain,
                                                         'resource_name': 'location',
                                                         'api_name': 'v0.3'}),
        'location': location,
        'hierarchy': location_hierarchy_config(domain),
        'form': form,
    }
    return render(request, 'locations/manage/location.html', context)


@domain_admin_required
@require_POST
def sync_facilities(request, domain):
    commtrack_settings = request.project.commtrack_settings

    # create Facility Registry and Facility LocationTypes if they don't exist
    if not any(lt.name == 'Facility Registry' 
               for lt in commtrack_settings.location_types):
        commtrack_settings.location_types.extend([
            LocationType(name='Facility Registry', allowed_parents=['']),
            LocationType(name='Facility', allowed_parents=['Facility Registry'])
        ])
        commtrack_settings.save()

    registry_locs = dict((l.external_id, l) for l in
            Location.filter_by_type(domain, 'Facility Registry'))

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

        facility_locs = dict((l.external_id, l) for l in
                Location.filter_by_type(domain, 'Facility', registry_loc))
        
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

@domain_admin_required
@require_POST
def sync_ilsgateway(request, domain):
    ils_bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')

