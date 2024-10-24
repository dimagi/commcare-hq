from lxml.builder import E

from casexml.apps.phone.fixtures import FixtureProvider

from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.case_search.filter_dsl import build_filter_from_xpath
from corehq.apps.es.case_search import CaseSearchES
from corehq.messaging.templating import (
    MessagingTemplateRenderer,
    NestedDictTemplateParam,
)


def _get_user_template_info(restore_user):
    return {
        "username": restore_user.username,
        "uuid": restore_user.user_id,
        "user_data": restore_user.user_session_data
    }


def _get_template_renderer(restore_user):
    renderer = MessagingTemplateRenderer()
    renderer.set_context_param('user', NestedDictTemplateParam(_get_user_template_info(restore_user)))
    return renderer


def _run_query(domain, csql):
    try:
        filter_ = build_filter_from_xpath(csql, domain=domain)
    except CaseFilterError:
        return "ERROR"
    return str(CaseSearchES()
               .domain(domain)
               .filter(filter_)
               .count())


def _get_indicator_nodes(domain, restore_user, indicators):
    renderer = _get_template_renderer(restore_user)
    for name, csql_template in indicators:
        value = _run_query(domain, renderer.render(csql_template))
        yield E.value(value, name=name)


class CaseSearchFixtureProvider(FixtureProvider):
    id = 'case-search-fixture'

    def __call__(self, restore_state):
        indicators = _get_indicators(restore_state.domain)
        if indicators:
            nodes = _get_indicator_nodes(restore_state.domain, restore_state.restore_user, indicators)
            yield E.fixture(E.values(*nodes), id=self.id)


def _get_indicators(domain):
    return []  # TODO


case_search_fixture_generator = CaseSearchFixtureProvider()
