from django.utils.translation import gettext as _, gettext_lazy

from corehq.apps.integration.kyc.models import KycVerificationStatus
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseSimpleFilter
from corehq.apps.reports.filters.users import WebUserFilter


class KycVerifiedByFilter(WebUserFilter):
    slug = 'verified_by'
    label = _('Verified by')


class KycVerificationStatusFilter(BaseSingleOptionFilter):
    slug = 'kyc_status'
    label = _('KYC Status')
    default_text = _('Show all')
    options = KycVerificationStatus.choices


class PhoneNumberFilter(BaseSimpleFilter):
    slug = 'phone_number'
    label = gettext_lazy('Phone number')
