from datetime import datetime, timedelta

from lxml.builder import E

from casexml.apps.phone.fixtures import FixtureProvider

from corehq import extensions
from corehq.apps.case_search.exceptions import CaseFilterError
from corehq.apps.case_search.filter_dsl import build_filter_from_xpath
from corehq.apps.es.case_search import CaseSearchES
from corehq.messaging.templating import (
    MessagingTemplateRenderer,
    NestedDictTemplateParam,
)
from corehq.toggles import MODULE_BADGES

from .models import CSQLFixtureExpression


def _get_user_template_info(restore_user):
    return {
        "username": restore_user.username,
        "uuid": restore_user.user_id,
        "user_data": restore_user.user_session_data,
        "location_ids": " ".join(restore_user.get_location_ids(restore_user.domain)),
    }


def _get_template_renderer(restore_user):
    renderer = MessagingTemplateRenderer()
    renderer.set_context_param('user', NestedDictTemplateParam(_get_user_template_info(restore_user)))
    for name, param in custom_csql_fixture_context(restore_user.domain, restore_user):
        renderer.set_context_param(name, param)
    return renderer


@extensions.extension_point
def custom_csql_fixture_context(domain, restore_user):
    '''Register custom template params to be available in CSQL templates'''


def _run_query(domain, csql):
    try:
        filter_ = build_filter_from_xpath(csql, domain=domain)
    except CaseFilterError:
        return "ERROR"
    return str(CaseSearchES()
               .domain(domain)
               .filter(filter_)
               .count())


class CaseSearchFixtureProvider(FixtureProvider):
    id = 'case-search-fixture'
    ignore_skip_fixtures_flag = True

    def __call__(self, restore_state):
        if not MODULE_BADGES.enabled(restore_state.domain):
            return
        indicators = _get_indicators(restore_state.domain)
        if indicators:
            with restore_state.timing_context('_get_template_renderer'):
                renderer = _get_template_renderer(restore_state.restore_user)
            for indicator in indicators:
                if self._should_sync(restore_state, indicator):
                    with restore_state.timing_context(indicator.name):
                        value = _run_query(restore_state.domain, renderer.render(indicator.csql))
                    yield self._to_xml(indicator.name, value)

    def _should_sync(self, restore_state, indicator):
        return not restore_state.use_cached_fixture(
            self._fixture_id(indicator.name),
            is_too_old=lambda last_sync_time: datetime.now() - last_sync_time > timedelta(minutes=10)
        )

    def _fixture_id(self, name):
        return f"{self.id}:{name}"

    def _to_xml(self, name, value):
        return E.fixture(E.value(value), id=self._fixture_id(name))


def _get_indicators(domain):
    return list(CSQLFixtureExpression.by_domain(domain))


case_search_fixture_generator = CaseSearchFixtureProvider()
