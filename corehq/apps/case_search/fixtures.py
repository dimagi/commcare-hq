from lxml.builder import E

from casexml.apps.phone.fixtures import FixtureProvider

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


def _run_query(csql):
    return "TODO"


def _get_indicator_node(name, csql_template, renderer):
    result = _run_query(renderer.render(csql_template))
    return E.value(result, name=name)


class CaseSearchFixtureProvider(FixtureProvider):
    id = 'case-search-fixture'

    def __call__(self, restore_state):
        renderer = _get_template_renderer(restore_state.restore_user)
        indicators = _get_indicators(restore_state.domain)
        if not indicators:
            return []
        return E.fixture(E.values(*[
            _get_indicator_node(name, csql_template, renderer)
            for name, csql_template in indicators
        ]), id=self.id)


def _get_indicators(domain):
    return []  # TODO


case_search_fixture_generator = CaseSearchFixtureProvider()
