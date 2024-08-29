from corehq.apps.reports.filters.base import CheckboxFilter


class RestrictedDomainsCheckbox(CheckboxFilter):
    label = "Show only restricted domains"
