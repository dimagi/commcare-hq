from corehq.apps.reports.filters.base import BaseSingleOptionFilter, CheckboxFilter
from django.utils.translation import ugettext_noop as _
from dimagi.utils.decorators.memoized import memoized
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


class DatePropFilter(BaseSingleOptionFilter):
    slug = 'date_prop'
    label = _("Filter by")
    default_text = _("Filter date by ...")

    @property
    def options(self):
        return [
            ('date_created', 'Date Created'),
            ('date_last_attempt', 'Date of Last Attempt'),
            ('date_next_attempt', 'Date of Next Attempt'),
        ]


class AttemptsFilter(CheckboxFilter):
    slug = 'filter_attempts'
    label = _("Show only records with max attempts")