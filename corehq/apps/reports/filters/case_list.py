from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext as _

from memoized import memoized

from corehq.apps.locations.permissions import location_safe
from corehq.apps.domain.models import Domain
from corehq.apps.reports.models import HQUserType
from .users import ExpandedMobileWorkerFilter, EmwfUtils


class CaseListFilterUtils(EmwfUtils):

    def sharing_group_tuple(self, g):
        return ("sg__%s" % g['_id'], '%s [case sharing]' % g['name'])

    @property
    @memoized
    def static_options(self):
        # Options to show in the filters are defined here
        hq_user_type_options = [HQUserType.DEACTIVATED, HQUserType.DEMO_USER,
                   HQUserType.ADMIN, HQUserType.WEB, HQUserType.UNKNOWN]
        if Domain.get_by_name(self.domain).commtrack_enabled:
            hq_user_type_options.append(HQUserType.COMMTRACK)

        # The static options themselves are created here. The options that are specific to the case list are added
        # first
        filters_to_display = [
            ("all_data", _("[All Data]")),
            ('project_data', _("[Project Data]"))
        ]
        filters_to_display.extend(self.create_static_option(option) for option in hq_user_type_options)
        
        return filters_to_display

    def _group_to_choice_tuple(self, group):
        if group.case_sharing:
            return self.sharing_group_tuple(group)
        else:
            return self.reporting_group_tuple(group)


@location_safe
class CaseListFilter(ExpandedMobileWorkerFilter):

    label = _("Case Owner(s)")
    slug = 'case_list_filter'
    options_url = 'case_list_options'
    default_selections = [('project_data', _("[Project Data]"))]
    placeholder = _("Add case owners to filter this report.")

    @property
    @memoized
    def utils(self):
        return CaseListFilterUtils(self.domain)

    @staticmethod
    def show_all_data(mobile_user_and_group_slugs):
        return 'all_data' in mobile_user_and_group_slugs

    @staticmethod
    def show_project_data(mobile_user_and_group_slugs):
        return 'project_data' in mobile_user_and_group_slugs

    @staticmethod
    def show_deactivated_data(mobile_user_and_group_slugs):
        from corehq.apps.reports.models import HQUserType
        return "t__{}".format(HQUserType.get_index(HQUserType.DEACTIVATED)) in mobile_user_and_group_slugs

    @staticmethod
    def selected_sharing_group_ids(mobile_user_and_group_slugs):
        return [g[4:] for g in mobile_user_and_group_slugs if g.startswith("sg__")]

    @classmethod
    def selected_group_ids(cls, mobile_user_and_group_slugs):
        return (super(CaseListFilter, cls).selected_group_ids(mobile_user_and_group_slugs) +
                cls.selected_sharing_group_ids(mobile_user_and_group_slugs))

    def _selected_group_entries(self, mobile_user_and_group_slugs):
        query_results = self._selected_groups_query(mobile_user_and_group_slugs)
        reporting = [self.utils.reporting_group_tuple(group)
                     for group in query_results
                     if group.get("reporting", False)]
        sharing = [self.utils.sharing_group_tuple(group)
                   for group in query_results
                   if group.get("case_sharing", False)]
        return reporting + sharing

    def get_default_selections(self):
        if self.request.can_access_all_locations:
            return self.default_selections
        else:
            return self._get_assigned_locations_default()
