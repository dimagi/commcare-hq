from django.http import (HttpResponse, HttpResponseNotFound,
    HttpResponseBadRequest, HttpResponseRedirect)
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.views.decorators.http import (require_GET, require_POST,
    require_http_methods)
from django.contrib import messages
from couchdbkit.exceptions import ResourceNotFound

from dimagi.utils.logging import notify_exception

from corehq.apps.domain.decorators import require_superuser
from .models import FacilityRegistry, Facility
from .forms import FacilityRegistryForm, FacilityForm


@require_GET
@require_superuser
def list_registries(request):
    return render(request, "facilities/list_registries.html", {
        'registries': FacilityRegistry.all()
    })


@require_http_methods(['GET', 'POST'])
@require_superuser
def add_view_or_update_registry(request, id=None):
    """Add, view, or update a facility registry"""

    if id:
        action = "edit"
        try:
            registry = FacilityRegistry.get(id)
        except ResourceNotFound:
            return HttpResponseNotFound()
    else:
        action = "create"
        registry = FacilityRegistry()

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
                    request, "Facility Registry successfully {0}d!".format(action))

                return HttpResponseRedirect(reverse(list_registries))
    else:
        form = FacilityRegistryForm(initial=registry.to_json())

    return render(request, "facilities/edit_registry.html", {
        'form': form,
        'action': action.capitalize()
    })


@require_GET
@require_superuser
def sync_registry(request, id, strategy='theirs'):
    try:
        registry = FacilityRegistry.get(id)
    except ResourceNotFound:
        return HttpResponseNotFound()

    registry.sync_with_remote(strategy=strategy)
    messages.success(request, "Facility Registry successfully synced!")
    return HttpResponseRedirect(reverse(list_registries))


@require_GET
@require_superuser
def delete_registry(request, id):
    try:
        registry = FacilityRegistry.get(id)
    except ResourceNotFound:
        return HttpResponseNotFound()

    try:
        registry.delete()
    except Exception:
        messages.error(request, "Error deleting facility!")
        notify_exception(request, "Error deleting facility {0}".format(id))
    else:
        messages.success(request, "Facility Registry successfully deleted!")

    return HttpResponseRedirect(reverse(list_registries))


@require_GET
@require_superuser
def list_facilities(request, registry_id=None):
    if registry_id:
        try:
            registry = FacilityRegistry.get(registry_id)
        except ResourceNotFound:
            return HttpResponseNotFound()
    else:
        registry = None

    return render(request, "facilities/list_facilities.html", {
        'registry': registry,
        'facilities': Facility.by_registry(registry_id).all()
    })


@require_http_methods(['GET', 'POST'])
@require_superuser
def view_or_update_facility(request, id):
    try:
        facility = Facility.get(id)
    except ResourceNotFound:
        return HttpResponseNotFound()

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
                        "Error using value {0} for the '{1}' field!".format(
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
                                                    args=(facility._id,)))
    else:
        form = FacilityForm(initial=facility.data)

    return render(request, "facilities/edit_facility.html", {
        'form': form
    })


@require_GET
@require_superuser
def delete_facility(request, id):
    try:
        facility = Facility.get(id)
    except ResourceNotFound:
        raise HttpResponseBadRequest()

    registry_id = facility.registry_id
    try:
        facility.delete()
        messages.success(request, "Facility successfully deleted!")
    except Exception:
        messages.error(request, "Error deleting facility!")
        notify_exception(request, "Error deleting facility {0}".format(id))

    return HttpResponseRedirect(reverse(list_facilities, args=(registry_id,)))
