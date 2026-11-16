from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from corehq.apps.document_templates.images import ImageError, share_images_with_linked_domain
from corehq.apps.document_templates.models import Template
from corehq.apps.linked_domain.exceptions import DomainLinkError


def update_linked_document_template(domain_link, upstream_template_id, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        raise DomainLinkError(_("Linking document templates to a remote link is not currently supported"))

    try:
        upstream_template = Template.objects.get(
            id=upstream_template_id, domain=domain_link.master_domain, deleted=False,
        )
    except Template.DoesNotExist:
        raise DomainLinkError(
            _("Document template does not exist in the upstream domain. Maybe it has been deleted?")
        )

    try:
        share_images_with_linked_domain(
            upstream_template.areas, domain_link.master_domain, domain_link.linked_domain)
    except ImageError as error:
        raise DomainLinkError(str(error))

    try:
        with transaction.atomic():
            Template.objects.update_or_create(
                domain=domain_link.linked_domain,
                upstream_id=upstream_template.id,
                defaults={
                    'name': upstream_template.name,
                    'slug': upstream_template.slug,
                    'areas': upstream_template.areas,
                    'deleted': False,
                },
            )
    except IntegrityError:
        raise DomainLinkError(
            _("Document template {slug} conflicts with an existing template in {domain}").format(
                slug=upstream_template.slug, domain=domain_link.linked_domain,
            )
        )
