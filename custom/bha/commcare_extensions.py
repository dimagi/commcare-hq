from django.conf import settings

from corehq.apps.case_search.fixtures import custom_csql_fixture_context
from corehq.messaging.templating import SimpleDictTemplateParam

from .util import get_user_clinic_ids, get_user_facility_ids

BHA_DOMAINS = settings.CUSTOM_DOMAINS_BY_MODULE['custom.bha']


@custom_csql_fixture_context.extend(domains=BHA_DOMAINS)
def bha_csql_fixture_context(domain, restore_user):
    facility_ids = get_user_facility_ids(domain, restore_user)
    return ('bha', SimpleDictTemplateParam({
        'facility_ids': ' '.join(facility_ids),
        'user_clinic_ids': get_user_clinic_ids(domain, restore_user, facility_ids),
    }))
