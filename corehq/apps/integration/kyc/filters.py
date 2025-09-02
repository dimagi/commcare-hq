from django.utils.translation import gettext as _, gettext_lazy

from corehq.apps.es.users import query_user_data
from corehq.apps.integration.kyc.models import KycVerificationStatus
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseSimpleFilter
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import WebUserFilter


class PhoneNumberFilter(BaseSimpleFilter):
    slug = 'phone_number'
    label = gettext_lazy('Phone number')



class KycVerificationStatusFilter(BaseSingleOptionFilter):
    slug = 'kyc_status'
    label = _('KYC status')
    default_text = _('Show all')
    options = KycVerificationStatus.choices()


# Filter Notes:

# Required filters:
# --- Location Case Owner filter
# - Case 1 : Custom User Data :Should not apply or we should filter mobile workers on how they are mapped to location
# TODO: Check if there is a filter for this

# - Case 2 : UserCases :Should not apply or we should filter mobile workers on how they are mapped to location. Can we use CaseSearch ES for this
# TODO: I think the user case is owned by user themselves, so case owner filter night not be a good fit here

# - Case 3 : Custom Case: Easy to add

# --- Phone number filter
# Should be dynamic as this column may not be available
# TODO: How to figure out the name of the field to filter on. Maybe add a config for this
# TODO : Phone number can be list in CommcareUser standard fields, figure out how this works
from corehq.apps.es import UserES, filters
from corehq.apps.es import CaseSearchES


# --- Case 1 : Custom User Data
# If field is part of custom user data, we can do search on UserES.
# If not (fallback), this is picked up from CommcareUser. So may we add an or query to UserES to search on phone_number field.
# TODO: Check how the OR query can be added to UserES
# --- Case 2 : UserCases :Should not apply or we should filter mobile workers on how they are mapped to location. Can we use CaseSearch ES for this
# TODO QUESTION: Are commcare user standard fields (like phone number) are present in UserCase - YES SORTED
# If yes, we can use do the same OR query as in Case 1

# ---Case 3 : Custom Case: Easy to add
# EASY TO DO

# - Status filter (to filter by verification status: All, Verified, Unverified, Failed)
# Should be easy to do for all scenarios.
# Custom user data is part of UserES

