from corehq.apps.accounting.filters import (
    clean_options,
    DateRangeFilter,
)
from django.utils.translation import ugettext_noop as _
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.sms.models import DIRECTION_CHOICES
from corehq.apps.smsbillables.models import SmsGatewayFeeCriteria, SmsBillable


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
            [(b, b) for b in SmsBillable.objects.values_list(
                'domain', flat=True).distinct()]
        )


class HasGatewayFeeFilter(BaseSingleOptionFilter):
    slug = 'has_gateway_fee'
    label = _('Has Gateway Fee')
    default_text = _('All')
    YES = "yes"
    NO = "no"
    options = (
        (YES, _('Yes')),
        (NO, _('No')),
    )


def get_criteria_property_options(property):
    return [
        (str(value), str(value))
        for value in SmsGatewayFeeCriteria.objects.values_list(property, flat=True).distinct()
    ]


class GatewayTypeFilter(BaseSingleOptionFilter):
    slug = 'gateway_type'
    label = _("Gateway Type")
    default_text = _("All")

    @property
    def options(self):
        return clean_options(get_criteria_property_options('backend_api_id'))


class SpecificGateway(BaseSingleOptionFilter):
    slug = 'specific_gateway'
    label = _("Specific Gateway")
    default_text = _("All")

    @property
    def options(self):
        return clean_options(get_criteria_property_options('backend_instance'))


class DirectionFilter(BaseSingleOptionFilter):
    slug = 'direction'
    label = _("Direction")
    default_text = _("All")
    options = DIRECTION_CHOICES


class CountryCodeFilter(BaseSingleOptionFilter):
    slug = 'country_code'
    label = _("Country Code")
    default_text = _("All")

    @property
    def options(self):
        return clean_options(get_criteria_property_options('country_code'))
