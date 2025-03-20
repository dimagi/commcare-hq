from django.utils.translation import gettext as _
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.integration.payments.services import get_payment_batch_numbers_for_domain


class PaymentVerificationStatusFilter(BaseSingleOptionFilter):
    slug = 'payment_verification_status'
    label = _("Verification Status")

    default_text = _('Select Verification Status')

    verified = 'verified'
    unverified = 'unverified'
    options = [
        (verified, _("Verified")),
        (unverified, _("Unverified")),
    ]


class BatchNumberFilter(BaseSingleOptionFilter):
    slug = "batch_number"
    label = _("Batch number")
    default_text = _("All batch numbers")

    @property
    def options(self):
        batch_numbers = get_payment_batch_numbers_for_domain(self.domain)
        return [
            (batch_number, batch_number) for batch_number in batch_numbers
        ]
