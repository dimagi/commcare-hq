from django.urls import reverse
from django.utils.translation import gettext_noop

from corehq.apps.locations.util import (
    load_locs_json,
    location_hierarchy_config,
)
from corehq.apps.reports.filters.base import BaseReportFilter


class AsyncLocationFilter(BaseReportFilter):
    # todo: cleanup template
    label = gettext_noop("Location")
    slug = "location_async"
    template = "reports/filters/bootstrap3/location_async.html"
    make_optional = False
    auto_drill = True

    @property
    def api_root(self):
        return reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                    'resource_name': 'location_internal',
                                                    'api_name': 'v0.5'})

    def load_locations_json(self, loc_id):
        return load_locs_json(self.domain, loc_id, user=self.request.couch_user)

    @property
    def location_hierarchy_config(self):
        return location_hierarchy_config(self.domain)

    @property
    def filter_context(self):
        api_root = self.api_root
        user = self.request.couch_user
        loc_id = self.request.GET.get('location_id')
        if not loc_id:
            # Don't use enterprise permissions, because any location not in the current domain won't exist
            domain_membership = user.get_domain_membership(self.domain, allow_enterprise=False)
            if domain_membership:
                loc_id = domain_membership.location_id
        return {
            'api_root': api_root,
            'control_name': self.label,  # todo: cleanup, don't follow this structure
            'control_slug': self.slug,  # todo: cleanup, don't follow this structure
            'auto_drill': self.auto_drill,
            'loc_id': loc_id,
            'locations': self.load_locations_json(loc_id),
            'make_optional': self.make_optional,
            'hierarchy': self.location_hierarchy_config,
            'path': self.request.path,
        }

    @classmethod
    def get_value(cls, request, domain):
        return request.GET.get('location_id')


class OptionalAsyncLocationFilter(AsyncLocationFilter):
    """
    This is the same as the AsyncLocationFilter, only when the template is
    rendered, it will give the user the option of filtering by location or
    not. If the user chooses to not filter by location, the location_id
    value will be blank.
    """
    make_optional = True
