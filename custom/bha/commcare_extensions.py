from django.conf import settings

from corehq.apps.case_search.fixtures import custom_csql_fixture_context
from corehq.messaging.templating import SimpleDictTemplateParam
from corehq.apps.es.case_search import CaseSearchES

BHA_DOMAINS = settings.CUSTOM_DOMAINS_BY_MODULE['custom.bha']


@custom_csql_fixture_context.extend(domains=BHA_DOMAINS)
def bha_csql_fixture_context(domain, restore_user):
    return ('bha', SimpleDictTemplateParam({
        'user_clinic_ids': _get_user_clinic_ids(domain, restore_user),
    }))


def _get_user_clinic_ids(domain, restore_user):
    return " ".join(
        CaseSearchES()
        .domain(domain)
        .case_type('clinic')
        .is_closed(False)
        .owner(restore_user.get_location_ids(domain))
        .get_ids()
    )
