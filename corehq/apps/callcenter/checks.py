from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from collections import namedtuple

from corehq.apps.callcenter.data_source import get_sql_adapters_for_domain
from corehq.apps.reports.analytics.esaccessors import get_form_counts_for_domains
from corehq.apps.reports.analytics.esaccessors import get_case_and_action_counts_for_domains

DataSourceStats = namedtuple(
    'DataSourceStats',
    [
        'name',
        'ucr_count', 'ucr_percent', 'ucr_css_class',
        'es_count', 'es_percent', 'es_css_class'
    ]
)


class DomainStats(namedtuple('DomainStats', 'name, forms, cases, case_actions, error')):
    def iter_data_source_stats(self):
        yield self.forms
        yield self.cases
        yield self.case_actions


def get_call_center_data_source_stats(domains):

    domains_to_forms = get_form_counts_for_domains(domains)
    domains_to_cases = get_case_and_action_counts_for_domains(domains)

    domain_data = {}
    for domain in domains:
        try:
            adapters = get_sql_adapters_for_domain(domain)
            domain_data[domain] = DomainStats(
                domain,
                forms=_compile_stats(
                    name='forms',
                    ucr_count=adapters.forms.get_query_object().count(),
                    es_count=domains_to_forms.get(domain, 0),
                ),
                cases=_compile_stats(
                    name='cases',
                    ucr_count=adapters.cases.get_query_object().count(),
                    es_count=domains_to_cases.get(domain, {}).get('cases', 0)
                ),
                case_actions=_compile_stats(
                    name='case_actions',
                    ucr_count=adapters.case_actions.get_query_object().count(),
                    es_count=domains_to_cases.get(domain, {}).get('case_actions', 0)
                ),
                error=None
            )
        except Exception as e:
            domain_data[domain] = DomainStats(domain, None, None, None, str(e))

    return domain_data


def _compile_stats(name, ucr_count, es_count):
    total = ucr_count + es_count

    def _percent(count):
        return 0 if total == 0 else 100 * count // total

    ucr_percent = _percent(ucr_count)
    es_percent = _percent(es_count)

    return DataSourceStats(
        name,
        ucr_count, ucr_percent, _get_css_class(ucr_percent, 'success'),
        es_count, es_percent, _get_css_class(es_percent, 'info')
    )


def _get_css_class(percent, default):
    for range in [(40, 'warning'), (30, 'danger')]:
        if percent <= range[0]:
            return range[1]

    if 5 >= percent or percent >= 95:
        return 'danger'

    return default
