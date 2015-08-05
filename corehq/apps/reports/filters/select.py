import datetime
import calendar

from django.conf import settings
from django.utils.translation import ugettext_lazy, ugettext as _
from corehq.apps.casegroups.dbaccessors import get_case_group_meta_in_domain

from corehq.apps.hqcase.dbaccessors import get_case_types_for_domain

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.groups.models import Group
from corehq.apps.orgs.models import Organization
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseMultipleOptionFilter


class SelectRegionFilter(BaseSingleOptionFilter):
    slug = "region"
    label = ugettext_lazy("Region")
    default_text = ugettext_lazy("All Regions")

    @property
    def options(self):
        if hasattr(Domain, 'regions'):
            available_regions = [(d.replace(' ', '+'), d) for d in Domain.regions()]
        else:
            available_regions = []
        return available_regions


class SelectLicenseFilter(BaseSingleOptionFilter):
    slug = "license"
    label = ugettext_lazy("License")
    default_text = ugettext_lazy("All Licenses")

    @property
    def options(self):
        return [(code, license_name) for code, license_name in LICENSES.items()]


class SelectCategoryFilter(BaseSingleOptionFilter):
    slug = "category"
    label = ugettext_lazy("Category")
    default_text = ugettext_lazy("All Categories")

    @property
    def options(self):
        if hasattr(Domain, 'categories'):
            available_categories = [(d.replace(' ', '+'), d) for d in Domain.categories()]
        else:
            available_categories = []
        return available_categories


class SelectOrganizationFilter(BaseSingleOptionFilter):
    slug = "org"
    label = ugettext_lazy("Organization")
    default_text = ugettext_lazy("All Organizations")

    @property
    def options(self):
        return [(o.name, o.title) for o in  Organization.get_all()]


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
        return [(case, "%s" % case) for case in case_types]


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
        apps_for_domain = Application.get_db().view(
            "app_manager/applications_brief",
            startkey=[self.domain],
            endkey=[self.domain, {}],
            include_docs=True
        ).all()
        return [(app['value']['_id'], _("%(name)s [up to build %(version)s]") % {
            'name': app['value']['name'],
            'version': app['value']['version']}) for app in apps_for_domain]


class MultiCaseGroupFilter(BaseMultipleOptionFilter):
    slug = "case_group"
    label = ugettext_lazy("Case Group")
    default_text = ugettext_lazy("All Case Groups")
    placeholder = ugettext_lazy('Click to select case groups')

    @property
    def options(self):
        return get_case_group_meta_in_domain(self.domain)
