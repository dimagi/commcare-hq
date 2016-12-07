from datetime import datetime

from corehq.apps.domain.models import Domain
from corehq.apps.locations.util import load_locs_json
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter
from dimagi.utils.decorators.memoized import memoized


def location_hierarchy_config(domain):
    return [
        (loc_type.name, [loc_type.parent_type.name if loc_type.parent_type else None])
        for loc_type in Domain.get_by_name(
            domain
        ).location_types if loc_type.code in ['state', 'district', 'block']
    ]


class ICDSMonthFilter(MonthFilter):

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or "%02d" % datetime.now().month


class IcdsLocationFilter(AsyncLocationFilter):

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
            'control_name': self.label,  # todo: cleanup, don't follow this structure
            'control_slug': self.slug,  # todo: cleanup, don't follow this structure
            'loc_id': loc_id,
            'locations': load_locs_json(self.domain, loc_id, user=user),
            'make_optional': self.make_optional,
            'hierarchy': location_hierarchy_config(self.domain)
        }
