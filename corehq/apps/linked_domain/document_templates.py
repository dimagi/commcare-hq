from django.utils.translation import gettext as _

from corehq.apps.document_templates.images import (
    ImageError,
    copy_images,
    expire_unused_images,
    keep_images,
)
from corehq.apps.document_templates.models import Template
from corehq.apps.linked_domain.exceptions import DomainLinkError


def update_linked_document_template(domain_link, upstream_slug, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        raise DomainLinkError(_("Linking document templates to a remote link is not currently supported"))

    try:
        upstream_template = Template.objects.get(
            slug=upstream_slug, domain=domain_link.master_domain, deleted=False,
        )
    except Template.DoesNotExist:
        raise DomainLinkError(
            _("Document template does not exist in the upstream domain. Maybe it has been deleted?")
        )

    old = Template.objects.filter(domain=domain_link.linked_domain, slug=upstream_slug, deleted=False).first()
    if old and not old.is_linked:
        raise DomainLinkError(
            _("Document template {slug} conflicts with an existing template in {domain}").format(
                slug=upstream_slug, domain=domain_link.linked_domain,
            )
        )

    try:
        areas = copy_images(upstream_template.areas, domain_link.master_domain, domain_link.linked_domain)
    except ImageError as error:
        raise DomainLinkError(str(error))

    template = old or Template(domain=domain_link.linked_domain, slug=upstream_slug, is_linked=True)
    old_areas = old.areas if old else None
    template.name = upstream_template.name
    template.areas = areas
    template.save()
    # after the save, so that the copies still expire if it fails
    keep_images(domain_link.linked_domain, areas)
    expire_unused_images(domain_link.linked_domain, old_areas, areas)
