from django.utils.translation import gettext_lazy as _

from corehq.apps.es.users import UserES
from corehq.apps.fixtures.models import LookupTableRow
from corehq.apps.integration.payments.const import (
    PaymentProperties,
    PaymentStatus,
)
from corehq.apps.reports.filters.base import (
    BaseSimpleFilter,
    BaseSingleOptionFilter,
)
from corehq.apps.reports.filters.case_list import CaseListFilter

LOOKUP_TABLE_TAG_PREFIX = 'payments_'


def get_lookup_table_values(domain, tag, column):
    """Return values from ``column`` of the lookup table tagged ``tag`` in
    ``domain``, in the table's natural ``sort_key`` order. Duplicates are
    preserved; callers decide how to present them. Returns ``[]`` if the
    table is not configured.
    """
    values = []
    for row in LookupTableRow.objects.iter_rows(domain, tag=tag):
        field_values = row.fields.get(column, [])
        if field_values:
            values.append(field_values[0].value)
    return values


class PaymentVerifiedByFilter(BaseSingleOptionFilter):
    slug = 'verified_by'
    label = _('Verified by')
    default_text = _('Show all')

    @property
    def options(self):
        query = UserES().domain(self.domain).web_users()
        return [
            (username, username) for username in query.values_list('username', flat=True)
        ]


class PaymentStatusFilter(BaseSingleOptionFilter):
    slug = 'payment_status'
    label = _('Payment status')
    default_text = _('Show all')
    options = PaymentStatus.choices


class PaymentCaseListFilter(CaseListFilter):
    default_selections = [("all_data", _("[All Data]"))]


class BaseLookupTableFilter(BaseSingleOptionFilter):
    """Filter whose options are sourced from a per-domain lookup table.

    Each subclass sets ``slug`` to its underlying case-property name. That
    same value is the lookup-table row's column name, and prefixed with
    ``LOOKUP_TABLE_TAG_PREFIX`` it is the table's tag. The prefix
    namespaces these tables so they don't collide with unrelated lookup
    tables a domain may already have under the bare case-property name.
    """
    default_text = _("Show all")

    @property
    def options(self):
        if not self.slug:
            raise NotImplementedError("Subclasses must define 'slug'")
        column = self.slug
        tag = LOOKUP_TABLE_TAG_PREFIX + column
        values = get_lookup_table_values(self.domain, tag, column)
        return [(v, v) for v in sorted({v for v in values if v})]


class BatchNumberFilter(BaseLookupTableFilter):
    slug = PaymentProperties.BATCH_NUMBER.value
    label = _("Batch number")


class CampaignFilter(BaseLookupTableFilter):
    slug = PaymentProperties.CAMPAIGN.value
    label = _('Campaign')


class ActivityFilter(BaseLookupTableFilter):
    slug = PaymentProperties.ACTIVITY.value
    label = _('Activity')


class FunderFilter(BaseLookupTableFilter):
    slug = PaymentProperties.FUNDER.value
    label = _('Funder')


class CampaignWorkerRoleFilter(BaseLookupTableFilter):
    slug = PaymentProperties.CAMPAIGN_WORKER_ROLE.value
    label = _('Campaign worker role')


class PhoneNumberFilter(BaseSimpleFilter):
    slug = 'phone_number'
    label = _('Phone number')
