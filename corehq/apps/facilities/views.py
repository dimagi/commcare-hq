from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib import messages
from couchdbkit.exceptions import ResourceNotFound

from dimagi.utils.logging import notify_exception

from corehq.apps.domain.decorators import domain_admin_required
from .models import FacilityRegistry, Facility
from .forms import FacilityRegistryForm, FacilityForm


def default(request, domain):
    return HttpResponseRedirect(reverse(list_registries, args=[domain]))


@require_GET
@domain_admin_required
def list_registries(request, domain):
    return render(request, "facilities/list_registries.html", {
        'domain': domain,
        'registries': FacilityRegistry.by_domain(domain)
    })


@require_http_methods(['GET', 'POST'])
@domain_admin_required
def add_view_or_update_registry(request, domain, id=None):
    """Add, view, or update a facility registry"""

    if id:
        try:
            registry = FacilityRegistry.get(id, domain=domain)
        except ResourceNotFound:
            raise Http404()
    else:
        registry = FacilityRegistry(domain=domain)

    if request.method == 'POST':
        form = FacilityRegistryForm(request.POST, initial=registry.to_json())
        if form.is_valid():
            try:
                for k, v in form.cleaned_data.items():
                    setattr(registry, k, v)
                registry.save()
            except Exception:
                messages.error(request, "Error saving registry, is it valid?")
            else:
                messages.success(
                    request, "Facility Registry successfully {0}!".format(
                        "edited" if id else "created"))

                return HttpResponseRedirect(reverse(
                        list_registries, args=[domain]))
    else:
        form = FacilityRegistryForm(initial=registry.to_json())

    return render(request, "facilities/edit_registry.html", {
        'form': form,
        'new': id
    })


@require_GET
@domain_admin_required
def sync_registry(request, domain, id, strategy='theirs'):
    try:
        registry = FacilityRegistry.get(id, domain=domain)
    except ResourceNotFound:
        raise Http404()

    registry.sync_with_remote(strategy=strategy)
    messages.success(request, "Facility Registry successfully synced!")
    return HttpResponseRedirect(reverse(list_registries, args=[domain]))


@require_GET
@domain_admin_required
def delete_registry(request, domain, id):
    try:
        registry = FacilityRegistry.get(id, domain=domain)
    except ResourceNotFound:
        raise Http404()

    try:
        registry.delete()
    except Exception:
        messages.error(request, "Error deleting facility!")
        notify_exception(request, "Error deleting facility {0}".format(id))
    else:
        messages.success(request, "Facility Registry successfully deleted!")

    return HttpResponseRedirect(reverse(list_registries, args=[domain]))


@require_GET
@domain_admin_required
def list_facilities(request, domain, registry_id=None):
    if registry_id:
        try:
            registry = FacilityRegistry.get(registry_id, domain=domain)
        except ResourceNotFound:
            raise Http404()
    else:
        registry = None

    return render(request, "facilities/list_facilities.html", {
        'domain': domain,
        'registry': registry,
        'facilities': Facility.by_registry(registry_id).all()
    })


@require_http_methods(['GET', 'POST'])
@domain_admin_required
def view_or_update_facility(request, domain, id):
    try:
        facility = Facility.get(id, domain=domain)
    except ResourceNotFound:
        raise Http404()

    if request.method == 'POST':
        form = FacilityForm(request.POST, initial={
            'name': facility.data['name'],
            'active': facility.data['active']
        })
        if form.is_valid():
            for k, v in form.cleaned_data.items():
                try:
                    facility.data[k] = v
                except Exception:
                    messages.warning(request,
                        "Unable to use value {0} for the '{1}' field!".format(
                            v, k))
            try:
                facility.save()
            except Exception:
                messages.error(request, "Error saving facility!")
                notify_exception(request,
                        "Error saving facility {0}".format(id))
            else:
                messages.success(request, "Facility successfully updated "
                                          "and synced with remote server!")
                return HttpResponseRedirect(reverse(view_or_update_facility,
                                                    args=[domain, facility._id]))
    else:
        form = FacilityForm(initial=facility.data)

    return render(request, "facilities/edit_facility.html", {
        'form': form
    })


@require_GET
@domain_admin_required
def delete_facility(request, domain, id):
    try:
        facility = Facility.get(id, domain=domain)
    except ResourceNotFound:
        raise HttpResponseBadRequest()

    registry_id = facility.registry_id
    try:
        facility.delete()
        messages.success(request, "Facility successfully deleted!")
    except Exception:
        messages.error(request, "Error deleting facility!")
        notify_exception(request, "Error deleting facility {0}".format(id))

    return HttpResponseRedirect(reverse( 
        list_facilities, args=[registry_id, domain]))
