from django.utils.translation import gettext_lazy

from corehq.apps.reports.filters.base import BaseSimpleFilter


class RepeaterPayloadIdFilter(BaseSimpleFilter):
    slug = "payload_id"
    label = gettext_lazy("Payload ID")


class SimpleUsername(BaseSimpleFilter):
    slug = 'username'
    label = gettext_lazy("Username")
    help_inline = gettext_lazy("One or more usernames, comma-separated. "
                               "Leave blank to include all users "
                               "(requires domain to limit the scope).")


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
    default_time = "00:00"
    help_inline = gettext_lazy("Optional. Leave blank to include the full day.")


class IPAddressFilter(BaseSimpleFilter):
    slug = 'ip_address'
    label = gettext_lazy("IP Address")
    help_inline = gettext_lazy(
        "Single IP, CIDR (/8, /16, /24, /32), or comma-separated. "
        "Example: 10.0.0.0/8, 192.168.1.1"
    )

    ALLOWED_CIDR = {8: 1, 16: 2, 24: 3, 32: None}  # suffix -> number of octets for prefix

    @staticmethod
    def parse_ip_input(raw_input):
        """Parse IP address filter input.

        Returns:
            list of (match_type, value) tuples on success, where match_type is
            "exact" or "startswith".
            None if any entry has an invalid CIDR suffix.
            Empty list if input is blank.
        """
        if not raw_input or not raw_input.strip():
            return []

        results = []
        for entry in raw_input.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if "/" in entry:
                ip, suffix = entry.rsplit("/", 1)
                try:
                    suffix_int = int(suffix)
                except ValueError:
                    return None
                if suffix_int not in IPAddressFilter.ALLOWED_CIDR:
                    return None
                octets_needed = IPAddressFilter.ALLOWED_CIDR[suffix_int]
                if octets_needed is None:
                    results.append(("exact", ip))
                else:
                    octets = ip.split(".")
                    prefix = ".".join(octets[:octets_needed]) + "."
                    results.append(("startswith", prefix))
            else:
                results.append(("exact", entry))
        return results


class BaseURLFilter(BaseSimpleFilter):
    template = "reports/filters/bootstrap3/textarea_with_select.html"
    placeholder = ''
    mode_slug = None  # override in subclass: e.g. 'url_include_mode'

    @property
    def selected_mode(self):
        return self.request.GET.get(self.mode_slug, 'contains')

    @property
    def filter_context(self):
        from corehq.apps.reports.util import DatatablesServerSideParams
        return {
            'default': DatatablesServerSideParams.get_value_from_request(
                self.request, self.slug, default_value=""
            ),
            'help_inline': self.help_inline,
            'mode_options': [("contains", "contains"), ("startswith", "starts with")],
            'selected_mode': self.selected_mode,
            'placeholder': self.placeholder,
        }


class URLIncludeFilter(BaseURLFilter):
    slug = 'url_include'
    label = gettext_lazy("URL Include")
    mode_slug = 'url_include_mode'
    placeholder = '/a/domain/api/v1/'
    help_inline = gettext_lazy(
        "One URL pattern per line. Patterns are OR'd together. "
        "Leave blank to include all URLs."
    )


class URLExcludeFilter(BaseURLFilter):
    slug = 'url_exclude'
    label = gettext_lazy("URL Exclude")
    mode_slug = 'url_exclude_mode'
    placeholder = '/a/domain/heartbeat/'
    help_inline = gettext_lazy(
        "One URL pattern per line. Matching rows are excluded. "
        "Patterns are OR'd (any match excludes the row)."
    )


class StatusCodeFilter(BaseSimpleFilter):
    slug = 'status_code'
    label = gettext_lazy("Status Code")
    help_inline = gettext_lazy(
        "Comma-separated status codes. Example: 200, 403, 500. "
        "Leave blank to include all."
    )

    @staticmethod
    def parse_status_codes(raw_input):
        """Parse comma-separated status codes.

        Returns a list of integers, or empty list if blank.
        Returns None if any entry is not a valid integer.
        """
        if not raw_input or not raw_input.strip():
            return []
        codes = []
        for entry in raw_input.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                codes.append(int(entry))
            except ValueError:
                return None
        return codes
