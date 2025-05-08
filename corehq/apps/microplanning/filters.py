from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class GPSDataFilter(BaseSingleOptionFilter):
    ALL = 'all'

    slug = "gps_data"
    label = gettext_lazy("GPS Data")
    default_text = gettext_lazy("Missing")
    help_text = gettext_lazy("Show cases that have missing GPS Data or All cases")

    @property
    def options(self):
        return [
            (GPSDataFilter.ALL, _('All'))
        ]

    @property
    def show_all(self):
        return self.get_value(self.request, self.domain) == GPSDataFilter.ALL
