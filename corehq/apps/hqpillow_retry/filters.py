from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from django.utils.translation import ugettext_noop as _
from pillow_retry.models import PillowError


class PillowFilter(BaseSingleOptionFilter):
    slug = 'pillow'
    label = _("Pillow Class")
    default_text = _("Filter by pillow...")

    @property
    def options(self):
        return [(p, p) for p in PillowError.get_pillows()]


class ErrorTypeFilter(BaseSingleOptionFilter):
    slug = 'error'
    label = _("Error Type")
    default_text = _("Filter by error type...")

    @property
    def options(self):
        return [(e, e) for e in PillowError.get_error_types()]
