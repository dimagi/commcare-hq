from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseDrilldownOptionFilter
from django.utils.translation import ugettext_lazy as _
from corehq.apps.groups.models import Group

ALL_DISTRICTS = 'All Districts'

ALL_CVSU_GROUP = 'a05a82e839f4e6c7dbeab2ff368757da'


class AgeFilter(BaseSingleOptionFilter):
    age_display_map = {
        "lt5": "Younger than 5",
        "5-18": "Between 5 and 18",
        "lt18": "Younger than 18",
        "gte18": "18 and older"
    }
    slug = "age"
    label = _("Age")
    default_text = _("All")
    options = age_display_map.items()


class GenderFilter(BaseSingleOptionFilter):
    slug = 'gender'
    label = _("Gender")
    default_text = _("All")
    options = [("male", "Male"),
               ("female", "Female")]


class GroupFilter(BaseSingleOptionFilter):
    slug = 'district'
    label = _("District")
    default_text = _("Filter districts...")

    @property
    def options(self):
        self.groups = Group.get_reporting_groups(self.domain)
        return [self.group_option(group.get_id, group.name) for group in self.groups]

    @property
    def selected(self):
        selected = super(GroupFilter, self).selected
        return selected or ALL_CVSU_GROUP

    def group_option(self, id, name):
        if id == ALL_CVSU_GROUP:
            return id, ALL_DISTRICTS

        return id, name


class GroupUserFilter(BaseDrilldownOptionFilter):
    slug = 'location'
    label = 'Location'

    @property
    def drilldown_map(self):
        grps = []
        groups = Group.get_reporting_groups(self.domain)
        for g in groups:
            grp = self.group_option(g)
            users = []
            for u in g.get_users(is_active=True, only_commcare=True):
                users.append(dict(val=u.get_id, text=u.raw_username))

            grp['next'] = users
            grps.append(grp)

        return grps

    def group_option(self, group):
        if group.get_id == ALL_CVSU_GROUP:
            return dict(val=group.get_id, text=ALL_DISTRICTS)

        return dict(val=group.get_id, text=group.name)

    @classmethod
    def get_labels(cls):
        return [
            ('District', 'Filter Districts...', 'district'),
            ('CVSU', 'All CVSUs', 'cvsu'),
        ]

    @classmethod
    def get_value(cls, request, domain):
        val, inst = super(GroupUserFilter, cls).get_value(request, domain)
        ret = {}
        for v in val:
            ret[v['slug']] = v['value']

        return ret

    @property
    def selected(self):
        selected = super(GroupUserFilter, self).selected
        return selected or [ALL_CVSU_GROUP]
