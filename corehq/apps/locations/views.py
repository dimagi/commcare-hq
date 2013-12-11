from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseServerError
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from corehq.apps.commtrack.views import BaseCommTrackManageView

from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.locations.models import Location
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.util import load_locs_json, location_hierarchy_config, dump_locations
from corehq.apps.commtrack.models import LocationType
from corehq.apps.facilities.models import FacilityRegistry
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.contrib import messages
from couchdbkit import ResourceNotFound
import urllib

from django.utils.translation import ugettext as _, ugettext_noop
from dimagi.utils.decorators.memoized import memoized
from custom.openlmis.tasks import bootstrap_domain_task
from soil.util import expose_download
import uuid
from corehq.apps.commtrack.tasks import import_locations_async
from soil import DownloadBase
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from soil.heartbeat import heartbeat_enabled, is_alive
from couchexport.models import Format



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
    page_title = ugettext_noop("Manage Locations")
    template_name = 'locations/manage/locations.html'

    @property
    def page_context(self):
        selected_id = self.request.GET.get('selected')
        return {
            'selected_id': selected_id,
            'locations': load_locs_json(self.domain, selected_id),
        }


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
    def location(self):
        try:
            return Location.get(self.location_id)
        except ResourceNotFound:
            raise Http404()

    @property
    def page_name(self):
        return mark_safe(_("Edit {name} <small>{type}</small>").format(
            name=self.location.name, type=self.location.location_type
        ))

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.location_id])


class FacilitySyncView(BaseLocationView):
    urlname = 'sync_facilities'
    page_title = ugettext_noop("Sync with External Systems")
    template_name = 'locations/facility_sync.html'

    @property
    def page_context(self):
        return {'lmis_config': self.domain_object.commtrack_settings.openlmis_config}


class EditLocationHierarchy(BaseLocationView):
    urlname = 'location_hierarchy'
    page_title = ugettext_noop("Location Hierarchy")
    template_name = 'locations/location_hierarchy.html'


class LocationImportStatusView(BaseLocationView):
    urlname = 'location_import_status'
    page_title = ugettext_noop('Location Import Status')
    template_name = 'locations/manage/import_status.html'

    @property
    def page_context(self):
        return {}

    def get(self, request, *args, **kwargs):
        context = {
            'domain': self.domain,
            'download_id': kwargs['download_id']
        }
        return render(request, 'locations/manage/import_status.html', context)


class LocationImportView(BaseLocationView):
    urlname = 'location_import'
    page_title = ugettext_noop('Upload Locations from Excel')
    template_name = 'locations/manage/import.html'

    @property
    def page_context(self):
        return {}

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('locs')
        if not upload:
            return HttpResponse(_('no file uploaded'))
        if not args:
            return HttpResponse(_('no domain specified'))

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


def location_importer_job_poll(request, domain, download_id, template="locations/manage/partials/status.html"):
    download_data = DownloadBase.get(download_id)
    is_ready = False

    if download_data is None:
        download_data = DownloadBase(download_id=download_id)
        try:
            if download_data.task.failed():
                return HttpResponseServerError()
        except (TypeError, NotImplementedError):
            # no result backend / improperly configured
            pass

    alive = True
    if heartbeat_enabled():
        alive = is_alive()

    context = RequestContext(request)

    if download_data.task.state == 'SUCCESS':
        is_ready = True
        context['result'] = download_data.task.result.get('messages')

    context['is_ready'] = is_ready
    context['is_alive'] = alive
    context['progress'] = download_data.get_progress()
    context['download_id'] = download_id
    return render_to_response(template, context_instance=context)


def location_export(request, domain):
    response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename=locations.xlsx'

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
