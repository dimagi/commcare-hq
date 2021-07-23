import json
from collections import Counter

from django.http import Http404, JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST

from corehq.apps.domain.decorators import login_and_domain_required, domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.decorators import require_enterprise_admin
from corehq.apps.registry.models import DataRegistry, RegistryInvitation


@require_enterprise_admin
@login_and_domain_required
def data_registries(request, domain):
    owned, invited = [], []
    for registry in DataRegistry.objects.visible_to_domain(domain):
        if registry.domain == domain:
            owned.append(_registry_list_context(domain, registry))
        else:
            invited.append(_registry_list_context(domain, registry))

    context = {
        'domain': domain,
        'owned_registries': owned,
        'invited_registries': invited,
        'current_page': {
            'title': _('Data Registries'),
            'page_name': _('Data Registries'),
        },
    }
    return render(request, "registry/registry_list.html", context)


def _registry_list_context(domain, registry):
    invitations = registry.invitations.all()
    domain_obj = Domain.get_by_name(registry.domain)
    other_domain_invitations = [
        invitation for invitation in invitations
        if not invitation.domain == domain
    ]
    context = {
        "domain_name": domain_obj.display_name() if domain_obj else registry.domain,
        "name": registry.name,
        "description": registry.description or '',
        "slug": registry.slug,
        "is_active": registry.is_active,
        "participator_count": len([
            invitation for invitation in other_domain_invitations
            if invitation.status == RegistryInvitation.STATUS_ACCEPTED
        ])
    }
    if domain == registry.domain:  # domain is owner
        status_counter = Counter([invitation.status for invitation in other_domain_invitations])
        context.update({
            "invitation_count": len(invitations),
            "accepted_invitation_count": status_counter[RegistryInvitation.STATUS_ACCEPTED],
            "pending_invitation_count": status_counter[RegistryInvitation.STATUS_PENDING],
            "rejected_invitation_count": status_counter[RegistryInvitation.STATUS_REJECTED]
        })
    else:
        for_this_domain = [invitation for invitation in invitations if invitation.domain == domain]
        context.update({
            "invitation": for_this_domain[0].to_json()
        })
    return context


@domain_admin_required
@require_POST
def accept_registry_invitation(request, domain):
    registry_slug = request.POST.get('registry_slug')
    invitation = _get_invitation_or_404(domain, registry_slug)

    if not invitation.is_accepted:
        invitation.accept(request.user)

    return JsonResponse(_registry_list_context(domain, invitation.registry))


@domain_admin_required
@require_POST
def reject_registry_invitation(request, domain):
    registry_slug = request.POST.get('registry_slug')
    invitation = _get_invitation_or_404(domain, registry_slug)

    if not invitation.is_rejected:
        invitation.reject(request.user)

    return JsonResponse(_registry_list_context(domain, invitation.registry))


def _get_invitation_or_404(domain, registry_slug):
    try:
        return RegistryInvitation.objects.get(
            registry__slug=registry_slug,
            domain=domain
        )
    except RegistryInvitation.DoesNotExist:
        raise Http404


@require_enterprise_admin
@login_and_domain_required
def edit_registry(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)
    if registry.domain != domain:
        return redirect("manage_registry_participation", domain, registry_slug)

    context = {
        "registry": {
            "domain": domain,
            "name": registry.name,
            "description": registry.description or '',
            "slug": registry.slug,
            "is_active": registry.is_active,
            "case_types": registry.case_types,
            "invitations": [
                invitation.to_json() for invitation in registry.invitations.all()
            ],
            "grants": [
                grant.to_json() for grant in registry.grants.all()
            ]
        },
        "available_case_types": ["patient", "household"],  # TODO
    }
    return render(request, "registry/registry_edit.html", context)


@domain_admin_required
@require_POST
def edit_registry_attr(request, domain, registry_slug, attr):
    registry = _get_registry_or_404(domain, registry_slug)
    if registry.domain != domain:
        return HttpResponseForbidden()

    if attr not in ["name", "description", "invitation"]:
        return HttpResponseBadRequest()

    if attr in ["name", "description"]:
        value = request.POST.get("value")
        if not value and attr == 'name':
            return HttpResponseBadRequest()

        setattr(registry, attr, value)
        registry.save()
    else:
        action = request.POST.get("action")
        domain = request.POST.get("domain")
        invitation_id = request.POST.get("id")
        if not all([action, domain, invitation_id]):
            return HttpResponseBadRequest()

        if action == "remove":
            try:
                invitation = registry.invitations.get(id=invitation_id)
            except RegistryInvitation.DoesNotExist:
                raise Http404(f"Project Space '{domain}' is not a participant.")

            if invitation.domain != domain:
                return HttpResponseBadRequest()

            invitation.delete()
    return JsonResponse({})


@domain_admin_required
def manage_registry_participation(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)
    if registry.domain == domain:
        return redirect("edit_registry", domain, registry_slug)
    context = {}
    return render(request, "registry/registry_manage_participation.html", context)


def _get_registry_or_404(domain, registry_slug):
    try:
        return DataRegistry.objects.visible_to_domain(domain).get(slug=registry_slug)
    except DataRegistry.DoesNotExist:
        raise Http404
