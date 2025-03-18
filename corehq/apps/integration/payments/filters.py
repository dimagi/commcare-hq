from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from django.utils.translation import gettext as _


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
