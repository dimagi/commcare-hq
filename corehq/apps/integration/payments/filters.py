from django.utils.translation import gettext as _

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.integration.payments.services import get_payment_batch_numbers_for_domain
from corehq.apps.reports.filters.users import WebUserFilter
from corehq.apps.integration.payments.const import PaymentStatus


class PaymentVerificationStatusFilter(BaseSingleOptionFilter):
    slug = 'payment_verification_status'
    label = _("Verification Status")
    default_text = _('Show all')

    verified = 'verified'
    unverified = 'unverified'
    options = [
        (verified, _("Verified")),
        (unverified, _("Unverified")),
    ]


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
