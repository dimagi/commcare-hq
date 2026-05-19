from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.es.users import UserES
from corehq.apps.integration.payments.const import PaymentStatus
from corehq.apps.reports.filters.base import (
    BaseSimpleFilter,
    BaseSingleOptionFilter,
)
from corehq.apps.reports.filters.case_list import CaseListFilter


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


class BatchNumberFilter(BaseSimpleFilter):
    slug = 'batch_number'
    label = gettext_lazy('Batch number')


class CampaignFilter(BaseSimpleFilter):
    slug = 'campaign'
    label = gettext_lazy('Campaign')


class ActivityFilter(BaseSimpleFilter):
    slug = 'activity'
    label = gettext_lazy('Activity')


class FunderFilter(BaseSimpleFilter):
    slug = 'funder'
    label = gettext_lazy('Funder')


class PhoneNumberFilter(BaseSimpleFilter):
    slug = 'phone_number'
    label = gettext_lazy('Phone number')
