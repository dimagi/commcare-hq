import calendar
import datetime

from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.export.models.incremental import IncrementalExport
from corehq.apps.groups.models import Group
from corehq.apps.reports.analytics.esaccessors import (
    get_case_types_for_domain,
)
from corehq.apps.reports.filters.base import (
    BaseMultipleOptionFilter,
    BaseSingleOptionFilter,
)
from corehq.motech.repeaters.const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
)
from corehq.motech.repeaters.dbaccessors import get_repeaters_by_domain


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
        years = [(str(y), y) for y in range(start_year, datetime.datetime.utcnow().year + 1)]
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
        case_types = sorted(get_case_types_for_domain(self.domain))
        return [(case, "%s" % case) for case in case_types
                if case != USER_LOCATION_OWNER_MAP_TYPE]


class CaseTypeFilter(CaseTypeMixin, BaseSingleOptionFilter):
    placeholder = ugettext_lazy('Click to select a case type')


class MultiCaseTypeFilter(CaseTypeMixin, BaseMultipleOptionFilter):
    placeholder = ugettext_lazy('Click to select case types')


class SelectOpenCloseFilter(BaseSingleOptionFilter):
    slug = "is_open"
    label = ugettext_lazy("Open / Closed")
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

    if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
        default_text = ugettext_lazy("Select Application")
    else:
        default_text = ugettext_lazy("Select Application [Latest Build Version]")

    @property
    def options(self):
        apps_for_domain = get_brief_apps_in_domain(self.domain)
        if settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS:
            return [(app.get_id, _("{name}".format(
                name=app.name))) for app in apps_for_domain
            ]
        else:
            return [(app.get_id, _("{name} [up to build {version}]".format(
                name=app.name,
                version=app.version))) for app in apps_for_domain
            ]


class RepeaterFilter(BaseSingleOptionFilter):
    slug = 'repeater'
    label = ugettext_lazy('Repeater')
    default_text = ugettext_lazy("All Repeaters")
    placeholder = ugettext_lazy('Click to select repeaters')

    @property
    def options(self):
        return [(r.get_id, str(r)) for r in self._get_repeaters()]

    def _get_repeaters(self):
        return get_repeaters_by_domain(self.domain)


class RepeatRecordStateFilter(BaseSingleOptionFilter):
    slug = "record_state"
    label = ugettext_lazy("Record Status")
    default_text = ugettext_lazy("Show All")

    @property
    def options(self):
        return [
            (RECORD_SUCCESS_STATE, _("Successful")),
            (RECORD_PENDING_STATE, _("Pending")),
            (RECORD_CANCELLED_STATE, _("Cancelled")),
            (RECORD_FAILURE_STATE, _("Failed")),
        ]


class IncrementalExportFilter(BaseSingleOptionFilter):
    slug = 'incremental_export_id'
    label = ugettext_lazy('Incremental Export')
    default_text = ugettext_lazy("All Incremental Exports")

    @property
    def options(self):
        return [(str(i[0]), i[1]) for i in IncrementalExport.objects.filter(
            domain=self.domain
        ).values_list('id', 'name').all()]
