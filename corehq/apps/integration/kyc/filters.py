from django.utils.translation import gettext as _

from corehq.apps.integration.kyc.models import KycVerificationStatus
from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class KycVerificationStatusFilter(BaseSingleOptionFilter):
    slug = 'kyc_status'
    label = _('KYC Status')
    default_text = _('Show all')
    options = KycVerificationStatus.choices()
