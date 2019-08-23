from datetime import datetime

import pytz

from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.common.filters import RestrictedAsyncLocationFilter
from memoized import memoized


def location_hierarchy_config(domain, location_types=None):
    location_types = location_types or ['state', 'district', 'block']
    return [
        (loc_type.name, [loc_type.parent_type.name if loc_type.parent_type else None])
        for loc_type in Domain.get_by_name(
            domain
        ).location_types if loc_type.code in location_types
    ]


# copy/paste from corehq.apps.location.utils
# added possibility to exclude test locations, test flag is custom added to the metadata in location object
def load_locs_json(domain, selected_loc_id=None, user=None, show_test=False):

    def loc_to_json(loc, project):
        return {
            'name': loc.name,
            'location_type': loc.location_type.name,  # todo: remove when types aren't optional
            'uuid': loc.location_id,
            'is_archived': loc.is_archived,
            'can_edit': True
        }

    project = Domain.get_by_name(domain)

    locations = SQLLocation.root_locations(domain)
    if not show_test:
        locations = [
            loc for loc in locations if loc.metadata.get('is_test_location', 'real') != 'test'
        ]

    loc_json = [loc_to_json(loc, project) for loc in locations]

    # if a location is selected, we need to pre-populate its location hierarchy
    # so that the data is available client-side to pre-populate the drop-downs
    if selected_loc_id:
        selected = SQLLocation.objects.get(
            domain=domain,
            location_id=selected_loc_id
        )

        lineage = selected.get_ancestors()

        parent = {'children': loc_json}
        for loc in lineage:
            children = loc.child_locations()
            # find existing entry in the json tree that corresponds to this loc
            try:
                this_loc = [k for k in parent['children'] if k['uuid'] == loc.location_id][0]
            except IndexError:
                # if we couldn't find this location the view just break out of the loop.
                # there are some instances in viewing archived locations where we don't actually
                # support drilling all the way down.
                break
            this_loc['children'] = [loc_to_json(loc, project) for loc in children]
            parent = this_loc

    return loc_json


class ICDSTableauFilterMixin(object):
    def __init__(self, request, domain=None, timezone=pytz.utc, parent_report=None,
                 css_label=None, css_field=None):
        css_label = 'col-xs-4 col-md-4 col-lg-4 control-label'
        css_field = 'col-xs-8 col-md-8 col-lg-8'
        super(ICDSTableauFilterMixin, self).__init__(
            request, domain, timezone, parent_report, css_label, css_field
        )


class ICDSMonthFilter(ICDSTableauFilterMixin, MonthFilter):

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or "%02d" % datetime.now().month


class ICDSYearFilter(ICDSTableauFilterMixin, YearFilter):
    pass


class IcdsLocationFilter(AsyncLocationFilter):

    def load_locations_json(self, loc_id):
        show_test = self.request.GET.get('include_test', False)
        return load_locs_json(self.domain, loc_id, user=self.request.couch_user, show_test=show_test)


class IcdsRestrictedLocationFilter(AsyncLocationFilter):

    @property
    def location_hierarchy_config(self):
        return location_hierarchy_config(self.domain)


class TableauLocationFilter(ICDSTableauFilterMixin, RestrictedAsyncLocationFilter):

    auto_drill = False

    @property
    def location_hierarchy_config(self):
        return location_hierarchy_config(
            self.domain,
            location_types=['state', 'district', 'block', 'supervisor', 'awc']
        )


class CasteFilter(ICDSTableauFilterMixin, BaseSingleOptionFilter):
    slug = 'caste'
    label = 'Caste'

    @property
    @memoized
    def selected(self):
        return super(CasteFilter, self).selected or self.options[0][0]

    @property
    def options(self):
        return [
            ('All', 'All'),
            ('ST', 'ST'),
            ('SC', 'SC'),
            ('OBC', 'OBC'),
            ('Others', 'Others'),
        ]


class MinorityFilter(ICDSTableauFilterMixin, BaseSingleOptionFilter):
    slug = 'minority'
    label = 'Minority'

    @property
    @memoized
    def selected(self):
        return super(MinorityFilter, self).selected or self.options[0][0]

    @property
    def options(self):
        return [
            ('All', 'All'),
            ('Yes', 'Yes'),
            ('No', 'No')
        ]


class DisabledFilter(ICDSTableauFilterMixin, BaseSingleOptionFilter):
    slug = 'disabled'
    label = 'Disabled'

    @property
    @memoized
    def selected(self):
        return super(DisabledFilter, self).selected or self.options[0][0]

    @property
    def options(self):
        return [
            ('All', 'All'),
            ('Yes', 'Yes'),
            ('No', 'No')
        ]


class ResidentFilter(ICDSTableauFilterMixin, BaseSingleOptionFilter):
    slug = 'resident'
    label = 'Resident'

    @property
    @memoized
    def selected(self):
        return super(ResidentFilter, self).selected or self.options[0][0]

    @property
    def options(self):
        return [
            ('All', 'All'),
            ('Permanent', 'Permanent'),
            ('Resident', 'Resident')
        ]


class MaternalStatusFilter(ICDSTableauFilterMixin, BaseSingleOptionFilter):
    slug = 'ccs_status'
    label = 'Maternal status'

    @property
    @memoized
    def selected(self):
        return super(MaternalStatusFilter, self).selected or self.options[0][0]

    @property
    def options(self):
        return [
            ('All', 'All'),
            ('Pregnant', 'Pregnant'),
            ('Lactating', 'Lactating')
        ]


class ChildAgeFilter(ICDSTableauFilterMixin, BaseSingleOptionFilter):
    slug = 'child_age_tranche'
    label = 'Child age'

    @property
    @memoized
    def selected(self):
        return super(ChildAgeFilter, self).selected or self.options[0][0]

    @property
    def options(self):
        return [
            ('All', 'All'),
            ('0-28 days', '0-28 days'),
            ('28 days - 6mo', '28 days - 6mo'),
            ('1 yr', '1 yr'),
            ('2 yr', '2 yr'),
            ('3 yr', '3 yr'),
            ('4 yr', '4 yr'),
            ('5 yr', '5 yr'),
            ('6 yr', '6 yr'),
        ]


class THRBeneficiaryType(ICDSTableauFilterMixin, BaseSingleOptionFilter):
    slug = 'thr_beneficiary_type'
    label = 'THR Beneficiary Type'

    @property
    @memoized
    def selected(self):
        return super(THRBeneficiaryType, self).selected or self.options[0][0]

    @property
    def options(self):
        return [
            ('All', 'All'),
            ('Child', 'Child'),
            ('Pregnant', 'Pregnant'),
            ('Lactating', 'Lactating'),
        ]
