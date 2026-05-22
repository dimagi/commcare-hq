from django.utils.translation import gettext_lazy as _

from corehq.apps.es.users import UserES
from corehq.apps.fixtures.models import LookupTableRow
from corehq.apps.integration.payments.const import (
    PaymentProperties,
    PaymentStatus,
)
from corehq.apps.reports.filters.base import (
    BaseReportFilter,
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

    The lookup table's tag is ``LOOKUP_TABLE_TAG_PREFIX + case_property`` and
    its row column name is ``case_property``. The prefix namespaces these
    tables so they don't collide with unrelated lookup tables a domain may
    already have under the bare case-property name.
    """
    default_text = _("Show all")
    case_property = None

    @property
    def options(self):
        if not self.case_property:
            raise NotImplementedError("Subclasses must define 'case_property'")
        column = self.case_property.value
        tag = LOOKUP_TABLE_TAG_PREFIX + column
        values = get_lookup_table_values(self.domain, tag, column)
        return [(v, v) for v in sorted({v for v in values if v})]


class BatchNumberFilter(BaseLookupTableFilter):
    slug = "batch_number"
    label = _("Batch number")
    case_property = PaymentProperties.BATCH_NUMBER


class CampaignFilter(BaseLookupTableFilter):
    slug = 'campaign'
    label = _('Campaign')
    case_property = PaymentProperties.CAMPAIGN


class ActivityFilter(BaseLookupTableFilter):
    slug = 'activity'
    label = _('Activity')
    case_property = PaymentProperties.ACTIVITY


class FunderFilter(BaseLookupTableFilter):
    slug = 'funder'
    label = _('Funder')
    case_property = PaymentProperties.FUNDER


class PhoneNumberFilter(BaseSimpleFilter):
    slug = 'phone_number'
    label = _('Phone number')


class CaseCreatedDateRangeFilter(BaseReportFilter):
    slug = 'date_range'
    label = _('Case creation date range')
    template = 'payments/filters/case_created_date_range.html'

    @property
    def filter_context(self):
        return {
            'startdate': self.request.GET.get('startdate', ''),
            'enddate': self.request.GET.get('enddate', ''),
            'timezone': self.timezone.zone,
        }
