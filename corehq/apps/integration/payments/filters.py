from django.utils.translation import gettext as _

from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE
from corehq.apps.es.case_search import get_case_property_unique_values
from corehq.apps.integration.payments.const import PaymentStatus, PaymentProperties
from corehq.apps.integration.payments.services import (
    get_payment_batch_numbers_for_domain,
)
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import WebUserFilter


class BatchNumberFilter(BaseSingleOptionFilter):
    slug = "batch_number"
    label = _("Batch number")
    default_text = _("Show all")

    @property
    def options(self):
        batch_numbers = get_payment_batch_numbers_for_domain(self.domain)
        return [
            (batch_number, batch_number) for batch_number in batch_numbers
        ]


class PaymentVerifiedByFilter(WebUserFilter):
    slug = 'verified_by'
    label = _('Verified by')


class PaymentStatusFilter(BaseSingleOptionFilter):
    slug = 'payment_status'
    label = _('Payment status')
    default_text = _('Show all')
    options = PaymentStatus.choices


class PaymentCaseListFilter(CaseListFilter):
    default_selections = [("all_data", _("[All Data]"))]


class CampaignFilter(BaseSingleOptionFilter):
    slug = 'campaign'
    label = _('Campaign')
    default_text = _('Show all')

    @property
    def options(self):
        values = get_case_property_unique_values(
            self.domain,
            MOMO_PAYMENT_CASE_TYPE,
            PaymentProperties.CAMPAIGN,
        )
        return [(value, value) for value in sorted(values)]
