from __future__ import absolute_import
from datetime import datetime

import pytz

from corehq.apps.domain.models import Domain
from corehq.apps.locations.util import load_locs_json
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.common.filters import RestrictedAsyncLocationFilter
from dimagi.utils.decorators.memoized import memoized


def location_hierarchy_config(domain, location_types=None):
    location_types = location_types or ['state', 'district', 'block']
    return [
        (loc_type.name, [loc_type.parent_type.name if loc_type.parent_type else None])
        for loc_type in Domain.get_by_name(
            domain
        ).location_types if loc_type.code in location_types
    ]


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

    auto_drill = False

    @property
    def location_hierarchy_config(self):
        return location_hierarchy_config(self.domain)

    @property
    def filter_context(self):
        api_root = self.api_root
        user = self.request.couch_user
        loc_id = self.request.GET.get('location_id')
        if not loc_id:
            domain_membership = user.get_domain_membership(self.domain)
            if domain_membership:
                loc_id = domain_membership.location_id

        return {
            'api_root': api_root,
            'auto_drill': self.auto_drill,
            'control_name': self.label,  # todo: cleanup, don't follow this structure
            'control_slug': self.slug,  # todo: cleanup, don't follow this structure
            'loc_id': loc_id,
            'locations': load_locs_json(self.domain, loc_id, user=user),
            'make_optional': self.make_optional,
            'hierarchy': self.location_hierarchy_config
        }


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
