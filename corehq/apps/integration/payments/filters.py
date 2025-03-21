from django.utils.translation import gettext as _

from corehq.apps.es import UserES
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseMultipleOptionFilter
from corehq.apps.integration.payments.services import get_payment_batch_numbers_for_domain


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


class PaymentVerifiedByFilter(BaseMultipleOptionFilter):
    slug = 'verified_by'
    label = _('Verified by')
    default_text = _('Show all')

    @property
    def options(self):
        query = UserES().domain(self.domain).web_users()
        return [
            user_details for user_details in query.values_list('username', 'username')
        ]


class PaymentStatus(BaseSingleOptionFilter):
    slug = 'payment_status'
    label = _('Payment status')
    default_text = _('Show all')

    submitted = 'submitted'
    not_submitted = 'not_submitted'
    submission_failed = 'submission_failed'

    @property
    def options(self):
        return [
            (self.submitted, _('Submitted')),
            (self.not_submitted, _('Not submitted')),
            (self.submission_failed, _('Submission failed')),
        ]
