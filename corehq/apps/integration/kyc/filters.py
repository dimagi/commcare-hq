from django.utils.translation import gettext as _, gettext_lazy

from corehq.apps.es.users import UserES
from corehq.apps.integration.kyc.models import KycVerificationStatus
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseSimpleFilter


class KycVerifiedByFilter(BaseSingleOptionFilter):
    slug = 'verified_by'
    label = _('Verified by')
    default_text = _('Show all')

    @property
    def options(self):
        query = UserES().domain(self.domain).web_users()
        return [
            user_details for user_details in query.values_list('username', 'username')
        ]


class KycVerificationStatusFilter(BaseSingleOptionFilter):
    slug = 'kyc_status'
    label = _('KYC Status')
    default_text = _('Show all')
    options = KycVerificationStatus.choices


class PhoneNumberFilter(BaseSimpleFilter):
    slug = 'phone_number'
    label = gettext_lazy('Phone number')
