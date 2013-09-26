from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _

class SelectPNCStatusFilter(BaseSingleOptionFilter):
    slug = "PNC_status"
    label = ugettext_noop("Status")
    default_text = ugettext_noop("Select PNC Status")

    @property
    def options(self):
        return [
            ('On Time', _("On Time")),
            ('Late', _("Late")),
        ]

class SelectBlockFilter(BaseSingleOptionFilter):
    slug = "block"
    label = ugettext_noop("Block")
    default_text = ugettext_noop("Select Block")

    @property
    def options(self):
        return [
        ]

class SelectSubCenterFilter(BaseSingleOptionFilter):
    slug = "sub_center"
    label = ugettext_noop("Sub Center")
    default_text = ugettext_noop("Select Sub Center")

    @property
    def options(self):
        return [
        ]
