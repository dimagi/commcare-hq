from django.utils.translation import gettext as _

from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.userreports.models import UCRExpression


def create_linked_ucr_expression(domain_link, ucr_expression_id):
    if domain_link.is_remote:
        raise DomainLinkError(_("Linking expressions to a remote link is not currently supported"))

    try:
        ucr_expression = UCRExpression.objects.get(id=ucr_expression_id, domain=domain_link.master_domain)
    except UCRExpression.DoesNotExist:
        raise DomainLinkError(
            _("Expression does not exist in the upstream domain")
        )

    if UCRExpression.objects.filter(
        name=ucr_expression.name,
        domain=domain_link.linked_domain,
    ).exists():
        raise DomainLinkError(
            _("Expression {name} already exists in the downstream domain {domain}").format(
                name=ucr_expression.name, domain=domain_link.linked_domain
            )
        )

    ucr_expression.upstream_id = ucr_expression.id
    ucr_expression.id = None
    ucr_expression.domain = domain_link.linked_domain
    ucr_expression.save()

    return ucr_expression.id


def update_linked_ucr_expression(domain_link, ucr_expression_id, is_pull=False, overwrite=False):
    try:
        linked_ucr_expression = UCRExpression.objects.get(id=ucr_expression_id)
    except UCRExpression.DoesNotExist:
        raise DomainLinkError(
            _("Linked Expression could not be found")
        )

    try:
        upstream_ucr_expression = UCRExpression.objects.get(id=linked_ucr_expression.upstream_id)
    except UCRExpression.DoesNotExist:
        raise DomainLinkError(
            _("Upstream Expression could not be found. Maybe it has been deleted?")
        )

    linked_ucr_expression.update_from_upstream(upstream_ucr_expression)
