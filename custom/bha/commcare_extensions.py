from django.conf import settings

from corehq.apps.case_search.fixtures import (
    custom_csql_fixture_context,
    custom_csql_fixture_expiration,
)
from corehq.messaging.templating import SimpleDictTemplateParam

from .util import (
    get_most_recent_referral,
    get_user_clinic_ids,
    get_user_facility_ids,
)

BHA_DOMAINS = settings.CUSTOM_DOMAINS_BY_MODULE['custom.bha']


@custom_csql_fixture_context.extend(domains=BHA_DOMAINS)
def bha_csql_fixture_context(domain, restore_user):
    facility_ids = get_user_facility_ids(domain, restore_user)
    return ('bha', SimpleDictTemplateParam({
        'facility_ids': ' '.join(facility_ids),
        'user_clinic_ids': get_user_clinic_ids(domain, restore_user, facility_ids),
    }))


@custom_csql_fixture_expiration.extend(domains=BHA_DOMAINS)
def bha_csql_fixture_expiration(domain, indicator):
    if indicator.name in ('incoming-referrals', 'outgoing-referrals'):

        def _referrals_changed(last_sync_time):
            if most_recent := get_most_recent_referral(domain):
                # TODO check that datatypes match
                return most_recent > last_sync_time
            return False
        return _referrals_changed
