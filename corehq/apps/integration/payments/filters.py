from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.case_importer.const import MOMO_PAYMENT_CASE_TYPE
from corehq.apps.es.case_search import get_case_property_unique_values
from corehq.apps.integration.payments.const import (
    PaymentProperties,
    PaymentStatus,
)
from corehq.apps.reports.filters.base import (
    BaseSimpleFilter,
    BaseSingleOptionFilter,
)
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import WebUserFilter


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


class BaseCasePropertyFilter(BaseSingleOptionFilter):
    default_text = _("Show all")
    case_property = None

    @property
    def options(self):
        if not self.case_property:
            raise NotImplementedError("Subclasses must define 'case_property'")
        values = get_case_property_unique_values(
            self.domain,
            MOMO_PAYMENT_CASE_TYPE,
            self.case_property,
        )
        return [(value, value) for value in sorted(values)]


class BatchNumberFilter(BaseCasePropertyFilter):
    slug = "batch_number"
    label = _("Batch number")
    case_property = PaymentProperties.BATCH_NUMBER


class CampaignFilter(BaseCasePropertyFilter):
    slug = 'campaign'
    label = _('Campaign')
    case_property = PaymentProperties.CAMPAIGN


class ActivityFilter(BaseCasePropertyFilter):
    slug = 'activity'
    label = _('Activity')
    case_property = PaymentProperties.ACTIVITY


class FunderFilter(BaseCasePropertyFilter):
    slug = 'funder'
    label = _('Funder')
    case_property = PaymentProperties.FUNDER


class PhoneNumberFilter(BaseSimpleFilter):
    slug = 'phone_number'
    label = gettext_lazy('Phone number')
