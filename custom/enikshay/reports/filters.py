from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from django.urls import reverse

from corehq.apps.reports.filters.base import BaseMultipleOptionFilter, BaseReportFilter, BaseSingleOptionFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.base import BaseSimpleFilter
from corehq.apps.reports_core.exceptions import FilterValueException
from corehq.apps.reports_core.filters import QuarterFilter as UCRQuarterFilter
from corehq.apps.userreports.reports.filters.choice_providers import LocationChoiceProvider
from custom.enikshay.reports.choice_providers import DistrictChoiceProvider
from custom.enikshay.reports.utils import StubReport

from django.utils.translation import ugettext_lazy as _

from memoized import memoized


class EnikshayLocationFilter(BaseMultipleOptionFilter):

    label = _('Location')
    slug = 'locations_id'
    choice_provider = LocationChoiceProvider

    @property
    def options(self):
        return []

    @property
    def selected(self):
        """
        Values returned by this method are displayed in select box
        It should return locations passed in GET parameters without their descendants
        :return: Selected locations without their descendants
        """
        location_ids = self.request.GET.getlist(self.slug)

        if len(location_ids) == 0 \
                and not self.request.couch_user.has_permission(self.request.domain, 'access_all_locations'):
            # Display the user's location in the filter if none is selected
            location_ids = self.request.couch_user.get_location_ids(self.request.domain)
        choice_provider = self.choice_provider(StubReport(domain=self.domain), None)
        # We don't include descendants here because they will show up in select box
        choice_provider.configure({'include_descendants': False})
        choices = choice_provider.get_choices_for_known_values(location_ids, self.request.couch_user)
        if not choices:
            return self.default_options
        else:
            return [
                {'id': choice.value, 'text': choice.display}
                for choice in choices
            ]

    @classmethod
    def get_value(cls, request, domain):
        selected = super(EnikshayLocationFilter, cls).get_value(request, domain)
        if len([_f for _f in selected if _f]) == 0 and not request.couch_user.has_permission(domain, 'access_all_locations'):
            # Force the user to select their assigned locations, otherwise selecting no locations will result in
            # all results being returned.
            selected = request.couch_user.get_location_ids(domain)
        choice_provider = cls.choice_provider(StubReport(domain=domain), None)
        choice_provider.configure({'include_descendants': True})
        selected_locations = [
            choice.value
            for choice in choice_provider.get_choices_for_known_values(selected, request.couch_user)
        ]
        return selected_locations

    @property
    def pagination_source(self):
        return reverse('enikshay_locations', kwargs={'domain': self.domain})

    @property
    def filter_context(self):
        context = super(EnikshayLocationFilter, self).filter_context
        context['endpoint'] = self.pagination_source
        return context


class DistrictLocationFilter(EnikshayLocationFilter):
    label = 'District'
    slug = 'district_ids'
    choice_provider = DistrictChoiceProvider

    @property
    def pagination_source(self):
        return reverse('enikshay_district_locations', kwargs={'domain': self.domain})


class EnikshayMigrationFilter(BaseSingleOptionFilter):
    slug = 'is_migrated'
    label = _('Filter migrated data')
    default_text = _('Show All')
    options = (
        ('1', 'Show only migrated from Nikshay'),
        ('0', 'Show only eNikshay'),
    )


class DateOfDiagnosisFilter(DatespanFilter):
    label = _('Date of Diagnosis')


class TreatmentInitiationDateFilter(DatespanFilter):
    label = _('Date of Treatment Initiation')


class PeriodFilter(BaseSingleOptionFilter):
    slug = 'period'
    label = _('Time Period')
    default_text = None
    options = (
        ("three_day", "Last 3 days"),
        ("one_week", "Last 7 days"),
        ("two_week", "Last 2 weeks"),
        ("month", "Last 30 days")
    )

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or self.options[0][0]


class VoucherStateFilter(BaseSingleOptionFilter):
    slug = "voucher_state"
    label = "Voucher State"
    default_text = "Show All"

    @property
    def options(self):
        return [
            ("available", "available"),
            ("fulfilled", "fulfilled"),
            ("approved", "approved"),
            ("paid", "paid"),
            ("rejected", "rejected"),
            ("expired", "expired"),
            ("cancelled", "cancelled"),
        ]


class VoucherIDFilter(BaseSimpleFilter):
    slug = "voucher_id"
    label = "Voucher Readable ID"
