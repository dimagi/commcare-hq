import json
from collections import Counter

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST, require_GET

from corehq import toggles
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.data_dictionary.util import get_data_dict_case_types
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.decorators import use_multiselect
from corehq.apps.registry.models import DataRegistry, RegistryInvitation
from corehq.apps.registry.utils import _get_registry_or_404, DataRegistryCrudHelper


@domain_admin_required
@require_GET
@toggles.DATA_REGISTRY.required_decorator()
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
        'section': {
            'page_name': 'Project Settings',
            'url': reverse("domain_settings_default", args=[domain]),
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
@require_GET
@toggles.DATA_REGISTRY.required_decorator()
@use_multiselect
def manage_registry(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)

    is_owner = registry.domain == domain
    all_invitations = list(registry.invitations.all())
    domain_invitation = [invitation for invitation in all_invitations if invitation.domain == domain][0]
    if is_owner:
        invitations = all_invitations
        grants = registry.grants.all()
        available_domains = BillingAccount.get_account_by_domain(domain).get_domains()
    else:
        invitations, available_domains = [], []
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
        "available_domains": available_domains,
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
        'section': {
            'page_name': 'Project Settings',
            'url': reverse("domain_settings_default", args=[domain]),
        },
    }
    return render(request, "registry/registry_edit.html", context)


@domain_admin_required
@require_POST
def accept_registry_invitation(request, domain):
    registry_slug = request.POST.get('registry_slug')
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    invitation = helper.accept_invitation(domain)
    return JsonResponse({"invitation": invitation.to_json()})


@domain_admin_required
@require_POST
def reject_registry_invitation(request, domain):
    registry_slug = request.POST.get('registry_slug')
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    invitation = helper.reject_invitation(domain)
    return JsonResponse({"invitation": invitation.to_json()})


@domain_admin_required
@require_POST
def edit_registry_attr(request, domain, registry_slug, attr):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)

    if helper.registry.domain != domain:
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
        case_types = request.POST.getlist("value")
        schema = [{"case_type": case_type} for case_type in case_types]
        helper.update_schema(schema)
        return JsonResponse({"schema": helper.registry.schema})
    elif attr == "is_active":
        value = json.loads(request.POST.get("value"))
        helper.set_active_state(value)
        return JsonResponse({"is_active": helper.registry.is_active})

    helper.set_attr(attr, value)
    return JsonResponse({attr: value})


@domain_admin_required
@require_POST
def manage_invitations(request, domain, registry_slug):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if helper.registry.domain != domain:
        return JsonResponse({"error": _("Action not permitted")}, status=403)

    action = request.POST.get("action")
    if action not in ("add", "remove"):
        return JsonResponse({"error": _("Unable to process your request")}, status=400)

    if action == "remove":
        invitation_domain = request.POST.get("domain")
        invitation_id = request.POST.get("id")
        if not all([domain, invitation_id]):
            return JsonResponse({"error": _("Unable to process your request")}, status=400)

        try:
            helper.remove_invitation(invitation_domain, invitation_id)
        except Http404:
            return JsonResponse({
                "error": _("Project Space '{domain}' is not a participant.").format(domain=invitation_domain)},
                status=404
            )
        except ValueError:
            return JsonResponse({"error": _("Unable to process your request")}, status=400)
        return JsonResponse({
            "message": _("Project Space '{domain}' removed").format(domain=domain)
        })

    if action == "add":
        domains = request.POST.getlist("domains")
        if not domains:
            return JsonResponse({"error": _("No Project Spaces specified")}, status=400)

        invitations = []
        for domain in domains:
            try:
                invitation, created = helper.get_or_create_invitation(domain)
                if created:
                    invitations.append(invitation)
            except ValueError:
                pass

        return JsonResponse({
            "invitations": [
                invitation.to_json() for invitation in invitations
            ],
            "message": _("{count} invitations sent").format(count=len(invitations))
        })


@domain_admin_required
@require_POST
def manage_grants(request, domain, registry_slug):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)

    action = request.POST.get("action")
    if action not in ("add", "remove"):
        return JsonResponse({"error": _("Unable to process your request")}, status=400)

    if action == "remove":
        grant_id = request.POST.get("id")

        try:
            grant = helper.remove_grant(from_domain=domain, grant_id=grant_id)
        except Http404:
            return JsonResponse({
                "error": _("Grant not found")},
                status=404
            )

        return JsonResponse({
            "message": _("Access removed from '{domain}' to '{domains}'").format(
                domain=domain,
                domains="', '".join(grant.to_domains)
            )
        })

    if action == "add":
        to_domains = request.POST.getlist("domains")
        if not to_domains:
            return JsonResponse({"error": _("No Project Spaces specified")}, status=400)

        try:
            grant, created = helper.get_or_create_grant(domain, to_domains)
        except ValueError as e:
            return JsonResponse({"error": str(e)})

        if created:
            return JsonResponse({
                "grants": [grant.to_json()],
                "message": _("Access granted from '{domain}' to '{domains}'").format(
                    domain=domain,
                    domains="', '".join(to_domains)
                )
            })
        return JsonResponse({
            "grants": [], "message": _("'{domains}' already have access.").format(domains="', '".join(to_domains))
        })


@domain_admin_required
@require_POST
def delete_registry(request, domain, registry_slug):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if helper.registry.domain != domain:
        messages.error(
            request,
            _("You do not have permission to delete the '{name}' registry").format(name=helper.registry.name)
        )
    else:
        helper.delete_registry()
        messages.success(request, _("Data Registry '{name}' deleted successfully").format(
            name=helper.registry.name
        ))

    return redirect("data_registries", domain=domain)
