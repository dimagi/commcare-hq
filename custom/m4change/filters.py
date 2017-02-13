from collections import defaultdict

from django.utils.translation import ugettext_noop, ugettext as _

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter


class FacilityHmisFilter(BaseSingleOptionFilter):
    slug = "facility_hmis_filter"
    label = ugettext_noop("Facility HMIS Report")
    default_text = None

    @property
    def options(self):
        from custom.m4change.reports import all_hmis_report, anc_hmis_report, immunization_hmis_report, \
            ld_hmis_report

        return [
            ("all", all_hmis_report.AllHmisReport.name),
            ("anc", anc_hmis_report.AncHmisReport.name),
            ("immunization", immunization_hmis_report.ImmunizationHmisReport.name),
            ("ld", ld_hmis_report.LdHmisReport.name),
        ]


class ServiceTypeFilter(BaseSingleOptionFilter):
    slug = "service_type_filter"
    label = ugettext_noop("Service type")
    default_text = None

    @property
    def options(self):
        return [
            ("all", _("All")),
            ("registration", _("registration")),
            ("antenatal", _("antenatal")),
            ("delivery", _("delivery")),
            ("immunization", _("immunization"))
        ]


class RestrictedLocationDrillDown(object):

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user

    def _get_path_to_first_common_parent(self):
        sql_locations = self.user.get_sql_locations(self.domain)
        list_of_ancestors = [
            sql_location.get_ancestors(ascending=True, include_self=True)
            for sql_location in sql_locations
        ]

        if list_of_ancestors:
            common_ancestors = set(list_of_ancestors[0])
            for ancestors in list_of_ancestors[1:]:
                common_ancestors = common_ancestors.intersection(set(ancestors))

            for ancestors in list_of_ancestors:
                for ancestor in ancestors:
                    yield ancestor
                    if ancestor in common_ancestors:
                        break

    def get_locations_json(self):
        def loc_to_json(loc):
            return {
                'pk': loc.pk,
                'name': loc.name,
                'location_type': loc.location_type.name,
                'uuid': loc.location_id,
                'is_archived': loc.is_archived,
                'level': loc.level,
                'parent_id': loc.parent_id
            }
        user = self.user

        user_locations = list(SQLLocation.objects.accessible_to_user(self.domain, user))
        if not user_locations:
            return []

        user_locations.extend(list(self._get_path_to_first_common_parent()))
        user_locations = list(set(user_locations))
        user_locations = [
            loc_to_json(sql_location)
            for sql_location in user_locations
        ]

        parent_to_location_map = defaultdict(list)

        for location in user_locations:
            parent_to_location_map[location['parent_id']].append(location)

        for location in user_locations:
            location['children'] = parent_to_location_map[location['pk']]

        min_level = min([location['level'] for location in user_locations])
        return filter(lambda x: x['level'] == min_level, user_locations)


class M4ChangeAsyncLocationFilter(AsyncLocationFilter):

    def load_locations_json(self, loc_id):
        user = self.request.couch_user
        if user.has_permission(self.domain, 'access_all_locations'):
            return super(M4ChangeAsyncLocationFilter, self).load_locations_json(loc_id)
        return RestrictedLocationDrillDown(domain=self.domain, user=user).get_locations_json()
