import json
from collections import Counter

from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy, gettext
from django.utils.functional import lazy

from corehq.apps.export.const import DEID_ID_TRANSFORM, DEID_DATE_TRANSFORM

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.app_schemas.case_properties import (
    all_case_properties_by_domain,
)
from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES,
    DOCS_LINK_CASE_LIST_EXPLORER,
)
from corehq.apps.data_dictionary.util import get_case_property_label_dict
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.reports.filters.base import (
    BaseSimpleFilter,
    BaseSingleOptionFilter,
)
from corehq import privileges


mark_safe_lazy = lazy(mark_safe, str)  # TODO: Replace with library method


class CaseSearchFilter(BaseSimpleFilter):
    slug = 'search_query'
    label = gettext_lazy("Search")

    @property
    def help_inline(self):
        from corehq import toggles
        cle_link = DOCS_LINK_CASE_LIST_EXPLORER
        if (domain_has_privilege(self.domain, privileges.CASE_LIST_EXPLORER)
                or toggles.CASE_LIST_EXPLORER.enabled(self.domain)):
            from corehq.apps.reports.standard.cases.case_list_explorer import CaseListExplorer
            cle_link = CaseListExplorer.get_url(domain=self.domain)
        return mark_safe(gettext(  # nosec: no user input
            'Enter <a href="https://wiki.commcarehq.org/display/commcarepublic/'
            'Advanced+Case+Search" target="_blank">targeted queries</a> to search across '
            'all specific columns of this report. For deeper searches by case properties use the '
            '<a href="{}">Case List Explorer</a>.'
        ).format(cle_link))


class DuplicateCaseRuleFilter(BaseSingleOptionFilter):
    slug = 'duplicate_case_rule'
    label = gettext_lazy("Duplicate Case Rule")

    @property
    def help_text(self):
        from corehq.apps.data_interfaces.views import DeduplicationRuleListView

        description = gettext(
            "Show cases that are determined to be duplicates based on this rule. "
            "You can further filter them with a targeted search below."
        )

        link = format_html(
            '<a href="{}" target="_blank">{}</a>',
            reverse(DeduplicationRuleListView.urlname, args=[self.domain]),
            gettext('View Rules')
        )

        return format_html('{} {}', description, link)

    @property
    def options(self):
        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
            deleted=False,
        )
        return [(
            str(rule.id),
            "{name} ({case_type}){active}".format(
                name=rule.name,
                case_type=rule.case_type,
                active="" if rule.active else gettext_lazy(" (Inactive)")
            )
        ) for rule in rules]


class XPathCaseSearchFilter(BaseSimpleFilter):
    """
    For report views use XpathCaseSearchFilterMixin to support this filter
    """
    slug = 'search_xpath'
    label = gettext_lazy("Search")
    template = "reports/filters/xpath_textarea.html"

    @property
    def filter_context(self):
        context = super(XPathCaseSearchFilter, self).filter_context
        context.update({
            'placeholder': "e.g. name = 'foo' and dob <= '2017-02-12'",
            'text': self.get_value(self.request, self.domain) or '',
            'suggestions': json.dumps(self.get_suggestions()),
        })

        return context

    def get_suggestions(self):
        case_properties = get_flattened_case_properties(self.domain, include_parent_properties=True)
        special_case_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in SPECIAL_CASE_PROPERTIES
        ]
        operators = [
            {'name': prop, 'case_type': None, 'meta_type': 'operator'}
            for prop in ['=', '!=', '>=', '<=', '>', '<', 'and', 'or']
        ]
        return case_properties + special_case_properties + operators


class CaseListExplorerColumns(BaseSimpleFilter):
    slug = 'explorer_columns'
    label = gettext_lazy("Columns")
    template = "reports/filters/explorer_columns.html"
    DEFAULT_COLUMNS = [
        {'name': '@case_type', 'label': '@case_type'},
        {'name': 'case_name', 'label': 'case_name'},
        {'name': 'last_modified', 'label': 'last_modified'}
    ]

    @property
    def filter_context(self):
        context = super(CaseListExplorerColumns, self).filter_context

        initial_values = self.get_value(self.request, self.domain)
        if not initial_values:
            initial_values = self.DEFAULT_COLUMNS

        context.update({
            'initial_value': json.dumps(initial_values),
            'column_suggestions': json.dumps(self.get_column_suggestions()),
        })
        return context

    def get_column_suggestions(self):
        case_properties = get_flattened_case_properties(self.domain, include_parent_properties=False)
        special_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA
        ]
        return case_properties + special_properties

    @classmethod
    def get_value(cls, request, domain):
        value = super(CaseListExplorerColumns, cls).get_value(request, domain)
        ret = json.loads(value or "[]")
        # convert legacy list of strings to list of dicts
        if ret and isinstance(ret[0], str):
            ret = [{
                'name': prop_name,
                'label': prop_name
            } for prop_name in ret]

        return ret


class SensitiveCaseProperties(CaseListExplorerColumns):
    slug = "sensitive_properties"
    label = gettext_lazy("De-identify options")
    template = "reports/filters/sensitive_columns.html"

    @property
    def filter_context(self):
        context = super(SensitiveCaseProperties, self).filter_context
        initial_values = self.get_value(self.request, self.domain)

        context.update({
            'initial_value': json.dumps(initial_values),
            'column_suggestions': json.dumps(self.get_column_suggestions()),
            'property_label_options': self.property_label_options
        })
        return context

    @property
    def property_label_options(self):
        return [
            {'type': DEID_ID_TRANSFORM, 'name': gettext_lazy('Sensitive ID')},
            {'type': DEID_DATE_TRANSFORM, 'name': gettext_lazy('Sensitive Date')},
        ]

    def get_column_suggestions(self):
        case_properties = get_flattened_case_properties(self.domain, include_parent_properties=False)
        special_properties = [
            {'name': prop, 'case_type': None, 'meta_type': 'info'}
            for prop in ('name', 'case_name', 'external_id')
        ]
        return case_properties + special_properties


def get_flattened_case_properties(domain, include_parent_properties=False):
    all_properties_by_type = all_case_properties_by_domain(
        domain,
        include_parent_properties=include_parent_properties
    )
    property_counts = Counter(item for sublist in all_properties_by_type.values() for item in sublist)

    if domain_has_privilege(domain, privileges.DATA_DICTIONARY):
        prop_labels = get_case_property_label_dict(domain)
        all_properties = [
            {
                'name': value,
                'case_type': case_type,
                'count': property_counts[value],
                'label': prop_labels.get(case_type, {}).get(value, value)
            }
            for case_type, values in all_properties_by_type.items()
            for value in values
        ]
    else:
        all_properties = [
            {'name': value, 'case_type': case_type, 'count': property_counts[value]}
            for case_type, values in all_properties_by_type.items()
            for value in values
        ]
    return all_properties
