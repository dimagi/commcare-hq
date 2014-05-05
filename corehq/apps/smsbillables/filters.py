from corehq import Domain
from corehq.apps.accounting.filters import (
    clean_options,
    DateRangeFilter,
)
from django.utils.translation import ugettext_noop as _
from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class DateSentFilter(DateRangeFilter):
    slug = 'date_sent'
    label = _("Date of Message")


class ShowBillablesFilter(BaseSingleOptionFilter):
    slug = 'show_billables'
    label = _("Show")
    default_text = _("All")
    VALID = "valid"
    INVALID = "invalid"
    options = (
        (VALID, _("Valid Billables")),
        (INVALID, _("Invalid Billables")),
    )


class DomainFilter(BaseSingleOptionFilter):
    slug = 'domain'
    label = _("Project Space")
    default_text = _("All")

    @property
    def options(self):
        return clean_options(
            [
                (domain.name, domain.name)
                for domain in Domain.get_all()
            ]
        )
