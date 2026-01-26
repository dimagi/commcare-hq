from django.utils.translation import gettext_lazy

from corehq.apps.reports.filters.base import BaseSimpleFilter


class RepeaterPayloadIdFilter(BaseSimpleFilter):
    slug = "payload_id"
    label = gettext_lazy("Payload ID")


class SimpleUsername(BaseSimpleFilter):
    slug = 'username'
    label = gettext_lazy("Username")
    help_inline = gettext_lazy("Leave this blank to include all users. "
                               "In that case, domain is required to limit the scope.")


class SimpleDomain(BaseSimpleFilter):
    slug = 'domain_name'
    label = gettext_lazy('Domain')


class SimpleOptionalDomain(SimpleDomain):
    help_inline = gettext_lazy('Optional')


class SimpleSearch(BaseSimpleFilter):
    slug = 'search_string'
    label = gettext_lazy('Search')


class BaseTimeFilter(BaseSimpleFilter):
    """
    A simple time input filter using HTML5 time input.
    Returns time in HH:MM format.
    """
    template = "reports/filters/bootstrap3/time_input.html"
    default_time = None  # Override in subclass, e.g., "00:00" or "23:59"

    @property
    def filter_context(self):
        from corehq.apps.reports.util import DatatablesServerSideParams
        return {
            'default': DatatablesServerSideParams.get_value_from_request(
                self.request, self.slug, default_value=self.default_time or ""
            ),
            'help_inline': self.help_inline
        }


class SimpleStartTime(BaseTimeFilter):
    slug = 'start_time'
    label = gettext_lazy("Start Time")
    default_time = "00:00"
    help_inline = gettext_lazy("Optional. Leave blank to use default (midnight).")


class SimpleEndTime(BaseTimeFilter):
    slug = 'end_time'
    label = gettext_lazy("End Time")
    default_time = "23:59"
    help_inline = gettext_lazy("Optional. Leave blank to use default (end of day).")
