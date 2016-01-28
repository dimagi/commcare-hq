import datetime
import calendar

from django.conf import settings
from django.utils.translation import ugettext_lazy, ugettext as _
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.casegroups.dbaccessors import get_case_group_meta_in_domain
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE

from corehq.apps.hqcase.dbaccessors import get_case_types_for_domain

from corehq.apps.app_manager.models import Application
from corehq.apps.groups.models import Group
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseMultipleOptionFilter


class GroupFilterMixin(object):
    slug = "group"
    label = ugettext_lazy("Group")
    default_text = ugettext_lazy("Everybody")

    @property
    def options(self):
        return [(group.get_id, group.name) for group in Group.get_reporting_groups(self.domain)]


class GroupFilter(GroupFilterMixin, BaseSingleOptionFilter):
    placeholder = ugettext_lazy('Click to select a group')


class MultiGroupFilter(GroupFilterMixin, BaseMultipleOptionFilter):
    placeholder = ugettext_lazy('Click to select groups')


class YearFilter(BaseSingleOptionFilter):
    slug = "year"
    label = ugettext_lazy("Year")
    default_text = None

    @property
    def options(self):
        start_year = getattr(settings, 'START_YEAR', 2008)
        years = [(unicode(y), y) for y in range(start_year, datetime.datetime.utcnow().year + 1)]
        years.reverse()
        return years


class MonthFilter(BaseSingleOptionFilter):
    slug = "month"
    label = ugettext_lazy("Month")
    default_text = None

    @property
    def options(self):
        return [("%02d" % m, calendar.month_name[m]) for m in range(1, 13)]


class CaseTypeMixin(object):
    slug = "case_type"
    label = ugettext_lazy("Case Type")
    default_text = ugettext_lazy("All Case Types")

    @property
    def options(self):
        case_types = get_case_types_for_domain(self.domain)
        return [(case, "%s" % case) for case in case_types
                if case != USER_LOCATION_OWNER_MAP_TYPE]


class CaseTypeFilter(CaseTypeMixin, BaseSingleOptionFilter):
    placeholder = ugettext_lazy('Click to select a case type')


class MultiCaseTypeFilter(CaseTypeMixin, BaseMultipleOptionFilter):
    placeholder = ugettext_lazy('Click to select case types')


class SelectOpenCloseFilter(BaseSingleOptionFilter):
    slug = "is_open"
    label = ugettext_lazy("Opened / Closed")
    default_text = ugettext_lazy("Show All")

    @property
    def options(self):
        return [
            ('open', _("Only Open")),
            ('closed', _("Only Closed")),
        ]


class SelectApplicationFilter(BaseSingleOptionFilter):
    slug = "app"
    label = ugettext_lazy("Application")
    default_text = ugettext_lazy("Select Application [Latest Build Version]")

    @property
    def options(self):
        apps_for_domain = get_brief_apps_in_domain(self.domain)
        return [(app.get_id, _("%(name)s [up to build %(version)s]") % {
            'name': app.name,
            'version': app.version}) for app in apps_for_domain]


class MultiCaseGroupFilter(BaseMultipleOptionFilter):
    slug = "case_group"
    label = ugettext_lazy("Case Group")
    default_text = ugettext_lazy("All Case Groups")
    placeholder = ugettext_lazy('Click to select case groups')

    @property
    def options(self):
        return get_case_group_meta_in_domain(self.domain)
