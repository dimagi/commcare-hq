from django.utils.translation import ugettext


from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.api import EmwfOptionsView
from corehq.apps.reports.util import _report_user_dict
from corehq.apps.users.cases import get_wrapped_owner
from corehq.apps.users.models import CommCareUser
from corehq.toggles import CALL_CENTER_LOCATION_OWNERS
from dimagi.utils.decorators.memoized import memoized


class _CallCenterOwnerOptionsUtils(object):
    def __init__(self, domain):
        self.domain = domain

    def user_tuple(self, user):
        user = _report_user_dict(user)
        name = "%s [user]" % user['username_in_report']
        return (user['user_id'], name)

    def reporting_group_tuple(self, group):
        return (group['_id'], '%s [group]' % group['name'])

    def location_tuple(self, location):
        return self.reporting_group_tuple(location.case_sharing_group_object())

    @property
    @memoized
    def static_options(self):
        from corehq.apps.domain.forms import USE_LOCATION_CHOICE
        from corehq.apps.domain.forms import USE_PARENT_LOCATION_CHOICE

        if CALL_CENTER_LOCATION_OWNERS.enabled(self.domain):
            return [
                (USE_LOCATION_CHOICE, ugettext("user's location [location]")),
                (USE_PARENT_LOCATION_CHOICE, ugettext("user's location's parent [location]")),
            ]
        return []


class CallCenterOwnerOptionsView(EmwfOptionsView):
    url_name = "call_center_owner_options"

    @property
    @memoized
    def utils(self):
        return _CallCenterOwnerOptionsUtils(self.domain)

    def get_locations_query(self, query):
        return (SQLLocation.objects
                .filter_path_by_user_input(self.domain, query)
                .filter(location_type__shares_cases=True))

    def group_es_query(self, query):
        return super(CallCenterOwnerOptionsView, self).group_es_query(query, "case_sharing")

    @property
    def data_sources(self):
        return [
            (self.get_static_options_size, self.get_static_options),
            (self.get_groups_size, self.get_groups),
            (self.get_locations_size, self.get_locations),
            (self.get_users_size, self.get_users),
        ]

    def user_es_query(self, query):
        q = super(CallCenterOwnerOptionsView, self).user_es_query(query)
        return q.mobile_users()

    @staticmethod
    def convert_owner_id_to_select_choice(owner_id, domain):
        utils = _CallCenterOwnerOptionsUtils(domain)
        for id, text in utils.static_options:
            if owner_id == id:
                return (id, text)

        owner = get_wrapped_owner(owner_id)
        if isinstance(owner, Group):
            return utils.reporting_group_tuple(owner)
        elif isinstance(owner, SQLLocation):
            return utils.location_tuple(owner)
        elif isinstance(owner, CommCareUser):
            return utils.user_tuple(owner)
        elif owner is None:
            return None
        else:
            raise Exception("Unexpcted owner type")
