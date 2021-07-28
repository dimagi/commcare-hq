import json
from collections import Counter

from django.contrib import messages
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST

from corehq.apps.data_dictionary.util import get_data_dict_case_types
from corehq.apps.domain.decorators import login_and_domain_required, domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.decorators import require_enterprise_admin
from corehq.apps.registry.models import DataRegistry, RegistryInvitation, RegistryGrant


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

    return JsonResponse({"invitation": invitation.to_json()})


@domain_admin_required
@require_POST
def reject_registry_invitation(request, domain):
    registry_slug = request.POST.get('registry_slug')
    invitation = _get_invitation_or_404(domain, registry_slug)

    if not invitation.is_rejected:
        invitation.reject(request.user)

    return JsonResponse({"invitation": invitation.to_json()})


def _get_invitation_or_404(domain, registry_slug):
    try:
        return RegistryInvitation.objects.get(
            registry__slug=registry_slug,
            domain=domain
        )
    except RegistryInvitation.DoesNotExist:
        raise Http404


@domain_admin_required
def manage_registry(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)

    is_owner = registry.domain == domain
    all_invitations = list(registry.invitations.all())
    domain_invitation = [invitation for invitation in all_invitations if invitation.domain == domain][0]
    if is_owner:
        invitations = all_invitations
        grants = registry.grants.all()
    else:
        invitations = []
        grants = registry.grants.filter(Q(from_domain=domain) | Q(to_domains__contains=[domain]))
    context = {
        "domain": domain,
        "is_owner": is_owner,
        "registry": {
            "domain": registry.domain,
            "current_domain": domain,
            "is_owner": is_owner,
            "name": registry.name,
            "description": registry.description or '',
            "slug": registry.slug,
            "is_active": registry.is_active,
            "schema": registry.case_types,
            "invitations": [invitation.to_json() for invitation in invitations if invitation.domain != domain],
            "domain_invitation": domain_invitation,
            "grants": [grant.to_json() for grant in grants]
        },
        "available_case_types": list(get_data_dict_case_types(registry.domain)),
        "available_domains": ["skelly", "d1"],  # TODO,
        "invited_domains": [invitation.domain for invitation in all_invitations],
        "current_page": {
            "title": "Manage Registry",
            "page_name": "Manage Registry",
            "parents": [
                {
                    "title": "Data Registries",
                    "page_name": "Data Registries",
                    "url": reverse("data_registries", args=[domain]),
                },
            ],
        },
    }
    return render(request, "registry/registry_edit.html", context)


@require_enterprise_admin
@require_POST
def edit_registry_attr(request, domain, registry_slug, attr):
    registry = _get_registry_or_404(domain, registry_slug)
    if registry.domain != domain:
        return JsonResponse({"error": _("Action not permitted")}, status=403)

    if attr not in ["name", "description", "schema", "is_active"]:
        return JsonResponse({"error": _("Unknown attribute")}, status=400)

    if attr == "name":
        value = request.POST.get("value")
        if not value:
            return JsonResponse({"error": _("'name' must not be blank")}, status=400)
    elif attr == "description":
        value = request.POST.get("value")
    elif attr == "schema":
        # TODO: fire signals to update UCRs
        case_types = request.POST.getlist("value")
        value = [{"case_type": case_type} for case_type in case_types]
    elif attr == "is_active":
        value = json.loads(request.POST.get("value"))

    setattr(registry, attr, value)
    registry.save()

    return JsonResponse({attr: value})


@require_enterprise_admin
@require_POST
def manage_invitations(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)
    if registry.domain != domain:
        return JsonResponse({"error": _("Action not permitted")}, status=403)

    action = request.POST.get("action")
    if action not in ("add", "remove"):
        return JsonResponse({"error": _("Unable to process your request")}, status=400)

    if action == "remove":
        domain = request.POST.get("domain")
        invitation_id = request.POST.get("id")
        if not all([domain, invitation_id]):
            return JsonResponse({"error": _("Unable to process your request")}, status=400)

        try:
            invitation = registry.invitations.get(id=invitation_id)
        except RegistryInvitation.DoesNotExist:
            return JsonResponse({
                "error": _("Project Space '{domain}' is not a participant.").format(domain=domain)},
                status=404
            )

        if invitation.domain != domain:
            return JsonResponse({"error": _("Incorrect Project Space")}, status=400)

        invitation.delete()
        return JsonResponse({
            "message": _("Project Space '{domain}' removed").format(domain=domain)
        })

    if action == "add":
        domains = request.POST.getlist("domains")
        if not domains:
            return JsonResponse({"error": _("No Project Spaces specified")}, status=400)

        invitations = []
        for domain in domains:
            # TODO: check that domain is part of the same account
            domain_obj = Domain.get_by_name(domain)
            if domain_obj:
                invitation, created = registry.invitations.get_or_create(domain=domain)
                if created:
                    invitations.append(invitation)

        return JsonResponse({
            "invitations": [
                invitation.to_json() for invitation in invitations
            ],
            "message": _("{count} invitations sent").format(count=len(invitations))
        })


@require_enterprise_admin
@require_POST
def manage_grants(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)

    action = request.POST.get("action")
    if action not in ("add", "remove"):
        return JsonResponse({"error": _("Unable to process your request")}, status=400)

    if action == "remove":
        grant_id = request.POST.get("id")

        try:
            grant = registry.grants.get(from_domain=domain, id=grant_id)
        except RegistryGrant.DoesNotExist:
            return JsonResponse({
                "error": _("Grant not found")},
                status=404
            )

        grant.delete()
        return JsonResponse({
            "message": _("Access removed from '{domain}' to '{domains}'").format(
                domain=domain,
                domains="', '".join(grant.to_domains)
            )
        })

    if action == "add":
        domains = set(request.POST.getlist("domains"))
        if not domains:
            return JsonResponse({"error": _("No Project Spaces specified")}, status=400)

        available_domains = set(registry.invitations.values_list("domain", flat=True))
        domains = domains & available_domains
        if not domains:
            return JsonResponse({"grants": []})

        grant, created = registry.grants.get_or_create(from_domain=domain, to_domains=list(domains))
        if created:
            return JsonResponse({
                "grants": [grant.to_json()],
                "message": _("Access granted from '{domain}' to '{domains}'").format(
                    domain=domain,
                    domains="', '".join(domains)
                )
            })
        return JsonResponse({
            "grants": [], "message": _("'{domains}' already have access.").format(domains="', '".join(domains))
        })


@require_enterprise_admin
@require_POST
def delete_registry(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)
    if registry.domain != domain:
        messages.success(
            request,
            _("You do not have permission to delete the '{name}' registry").format(name=registry.name)
        )
    else:
        messages.success(request, _("Data Registry '{name}' deleted successfully").format(name=registry.name))

    return redirect("data_registries", domain=domain)


def _get_registry_or_404(domain, registry_slug):
    try:
        return DataRegistry.objects.visible_to_domain(domain).get(slug=registry_slug)
    except DataRegistry.DoesNotExist:
        raise Http404
