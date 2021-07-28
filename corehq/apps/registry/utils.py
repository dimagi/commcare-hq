from django.http import Http404

from corehq.apps.registry.models import DataRegistry, RegistryInvitation


def _get_registry_or_404(domain, registry_slug):
    try:
        return DataRegistry.objects.visible_to_domain(domain).get(slug=registry_slug)
    except DataRegistry.DoesNotExist:
        raise Http404


def _get_invitation_or_404(domain, registry_slug):
    try:
        return RegistryInvitation.objects.get(
            registry__slug=registry_slug,
            domain=domain
        )
    except RegistryInvitation.DoesNotExist:
        raise Http404
