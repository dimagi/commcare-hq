from django.http import HttpResponse, HttpResponseRedirect, Http404
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.locations.models import Location
from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.util import load_locs_json, location_hierarchy_config
from corehq.apps.commtrack.models import LocationType
from corehq.apps.facilities.models import FacilityRegistry
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.contrib import messages
from couchdbkit import ResourceNotFound
import urllib

@domain_admin_required # TODO: will probably want less restrictive permission
def locations_list(request, domain):
    selected_id = request.GET.get('selected')

    context = {
        'domain': domain,
        'selected_id': selected_id,
        'locations': load_locs_json(domain, selected_id),
        'hierarchy': location_hierarchy_config(domain),
        'api_root': reverse('api_dispatch_list', kwargs={'domain': domain,
                                                         'resource_name': 'location', 
                                                         'api_name': 'v0.3'})
    }
    return render(request, 'locations/manage/locations.html', context)

@domain_admin_required # TODO: will probably want less restrictive permission
def location_edit(request, domain, loc_id=None):
    parent_id = request.GET.get('parent')

    if loc_id:
        try:
            location = Location.get(loc_id)
        except ResourceNotFound:
            raise Http404
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

