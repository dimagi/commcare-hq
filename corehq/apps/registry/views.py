import json
from collections import Counter
from datetime import datetime

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import gettext as _, ngettext
from django.views.decorators.http import require_POST, require_GET

from corehq import toggles
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.data_dictionary.util import get_data_dict_case_types
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.decorators import use_bootstrap5, use_multiselect, use_tempusdominus
from corehq.apps.registry.models import DataRegistry, RegistryInvitation
from corehq.apps.registry.utils import (
    _get_registry_or_404,
    DataRegistryCrudHelper,
    DataRegistryAuditViewHelper,
    manage_some_registries_required,
    manage_all_registries_required,
    RegistryPermissionCheck,
)
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user
from dimagi.utils.parsing import ISO_DATE_FORMAT


@manage_some_registries_required
@require_GET
@toggles.DATA_REGISTRY.required_decorator()
@use_bootstrap5
def data_registries(request, domain):
    owned, invited = [], []
    permission_check = RegistryPermissionCheck(domain, request.couch_user)
    for registry in DataRegistry.objects.visible_to_domain(domain):
        if not permission_check.can_manage_registry(registry.slug):
            continue
        if registry.domain == domain:
            owned.append(_registry_list_context(domain, registry))
        else:
            invited.append(_registry_list_context(domain, registry))

    context = {
        'domain': domain,
        'allow_create': permission_check.can_manage_all,
        'owned_registries': owned,
        'invited_registries': invited,
        'available_case_types': list(get_data_dict_case_types(domain)),
        'current_page': {
            'title': _('Data Registries'),
            'page_name': _('Data Registries'),
        },
        'section': {
            'page_name': _('Project Settings'),
            'url': reverse("domain_settings_default", args=[domain]),
        },
    }
    return render(request, "registry/registry_list.html", context)


def _registry_list_context(domain, registry):
    invitations = registry.invitations.all()
    domain_obj = Domain.get_by_name(registry.domain)
    status_counter = Counter([invitation.status for invitation in invitations])
    context = {
        "domain_name": domain_obj.display_name() if domain_obj else registry.domain,
        "name": registry.name,
        "description": registry.description or '',
        "slug": registry.slug,
        "is_active": registry.is_active,
        "participator_count": status_counter[RegistryInvitation.STATUS_ACCEPTED]
    }
    if domain == registry.domain:  # domain is owner
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


@manage_some_registries_required
@require_GET
@toggles.DATA_REGISTRY.required_decorator()
@use_bootstrap5
@use_multiselect
@use_tempusdominus
def manage_registry(request, domain, registry_slug):
    registry = _get_registry_or_404(domain, registry_slug)
    if not RegistryPermissionCheck(domain, request.couch_user).can_manage_registry(registry.slug):
        return HttpResponseForbidden()

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
            "schema": registry.wrapped_schema.case_types,
            "invitations": [invitation.to_json() for invitation in invitations if invitation.domain != domain],
            "domain_invitation": domain_invitation,
            "grants": [grant.to_json() for grant in grants]
        },
        "available_case_types": list(get_data_dict_case_types(registry.domain)),
        "available_domains": available_domains,
        "invited_domains": [invitation.domain for invitation in all_invitations],
        "log_action_types": DataRegistryAuditViewHelper.action_options(is_owner),
        "user_timezone": get_timezone_for_user(request.couch_user, domain),
        "current_page": {
            "title": _("Manage Registry"),
            "page_name": _("Manage Registry"),
            "parents": [
                {
                    "title": _("Data Registries"),
                    "page_name": _("Data Registries"),
                    "url": reverse("data_registries", args=[domain]),
                },
            ],
        },
        'section': {
            'page_name': _('Project Settings'),
            'url': reverse("domain_settings_default", args=[domain]),
        },
    }
    return render(request, "registry/registry_edit.html", context)


@manage_some_registries_required
@require_POST
def accept_registry_invitation(request, domain):
    registry_slug = request.POST.get('registry_slug')
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if not helper.check_permission(request.couch_user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    invitation = helper.accept_invitation(domain)
    return JsonResponse({"invitation": invitation.to_json()})


@manage_some_registries_required
@require_POST
def reject_registry_invitation(request, domain):
    registry_slug = request.POST.get('registry_slug')
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if not helper.check_permission(request.couch_user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    invitation = helper.reject_invitation(domain)
    return JsonResponse({"invitation": invitation.to_json()})


@manage_some_registries_required
@require_POST
def edit_registry_attr(request, domain, registry_slug, attr):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if not helper.check_permission(request.couch_user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    if helper.registry.domain != domain:
        return JsonResponse({"error": _("Action not permitted")}, status=403)

    if attr not in ["name", "description", "schema", "is_active"]:
        return JsonResponse({"error": _("Unknown attribute")}, status=400)

    if attr == "name":
        value = request.POST.get("value")
        if not value:
            return JsonResponse({"error": _("'name' must not be blank")}, status=400)
        if DataRegistry.objects.filter(name=value).exclude(id=helper.registry.id).exists():
            return JsonResponse({"error": _("'name' must be unique")}, status=400)
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


@manage_some_registries_required
@require_POST
def manage_invitations(request, domain, registry_slug):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if not helper.check_permission(request.couch_user):
        return JsonResponse({"error": "Permission denied"}, status=403)

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
            "message": _("Project Space '{domain}' removed").format(domain=invitation_domain)
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
            "message": ngettext(
                "{count} invitation sent",
                "{count} invitations sent",
                len(invitations)
            ).format(count=len(invitations))
        })


@manage_some_registries_required
@require_POST
def manage_grants(request, domain, registry_slug):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if not helper.check_permission(request.couch_user):
        return JsonResponse({"error": "Permission denied"}, status=403)

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
            return JsonResponse({"error": str(e)}, status=400)

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


@manage_some_registries_required
@require_POST
def delete_registry(request, domain, registry_slug):
    helper = DataRegistryCrudHelper(domain, registry_slug, request.user)
    if not helper.check_permission(request.couch_user):
        return JsonResponse({"error": "Permission denied"}, status=403)

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


@manage_all_registries_required
@require_POST
def create_registry(request, domain):
    name = request.POST.get("name")
    description = request.POST.get("description")
    case_types = request.POST.getlist("case_types")

    if not name:
        messages.error(request, _("Registry 'name' is required"))
        return redirect("data_registries", domain=domain)

    if not case_types:
        messages.error(request, _("Registry 'case types' is required"))
        return redirect("data_registries", domain=domain)

    if DataRegistry.objects.filter(name=name).exists():
        messages.error(request, _("Registry 'name' must be unique"))
        return redirect("data_registries", domain=domain)

    schema = [{"case_type": case_type} for case_type in case_types]
    registry = DataRegistry.create(
        request.user, domain, name,
        description=description, schema=schema
    )
    return redirect("manage_registry", domain=domain, registry_slug=registry.slug)


@manage_all_registries_required
@require_POST
def validate_registry_name(request, domain):
    name = request.POST.get("name")
    if not name:
        return JsonResponse({"result": False})

    exists = DataRegistry.objects.filter(name=name).exists()
    return JsonResponse({"result": not exists})


@manage_some_registries_required
@require_GET
def registry_audit_logs(request, domain, registry_slug):
    helper = DataRegistryAuditViewHelper(domain, registry_slug)

    if not RegistryPermissionCheck(domain, request.couch_user).can_manage_registry(registry_slug):
        return JsonResponse({"error": "Permission denied"}, status=403)

    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))
    skip = limit * (page - 1)

    try:
        start_date = _get_date_param(request, 'startDate')
        end_date = _get_date_param(request, 'endDate')
    except ValueError:
        return JsonResponse({"error": "Invalid date parameter"})

    domain_param = request.GET.get('domain') or None
    action = request.GET.get('action') or None

    helper.filter(domain_param, start_date, end_date, action)

    timezone = get_timezone_for_user(request.couch_user, domain)
    logs = helper.get_logs(skip, limit)
    for log in logs:
        log['date'] = ServerTime(log['date']).user_time(timezone).done().isoformat()

    return JsonResponse({
        "total": helper.get_total(),
        "logs": logs
    })


def _get_date_param(request, param_name):
    param = request.GET.get(param_name) or None
    if param:
        return datetime.strptime(param, ISO_DATE_FORMAT)
