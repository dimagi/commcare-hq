import datetime
import calendar
from django.conf import settings
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.groups.models import Group
from corehq.apps.orgs.models import Organization
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseMultipleOptionTypeaheadFilter


class SelectRegionFilter(BaseSingleOptionFilter):
    slug = "region"
    label = ugettext_noop("Region")
    default_text = ugettext_noop("All Regions")

    @property
    def options(self):
        if hasattr(Domain, 'regions'):
            available_regions = [(d.replace(' ', '+'), d) for d in Domain.regions()]
        else:
            available_regions = []
        return available_regions


class SelectLicenseFilter(BaseSingleOptionFilter):
    slug = "license"
    label = ugettext_noop("License")
    default_text = ugettext_noop("All Licenses")

    @property
    def options(self):
        return [(code, license_name) for code, license_name in LICENSES.items()]


class SelectCategoryFilter(BaseSingleOptionFilter):
    slug = "category"
    label = ugettext_noop("Category")
    default_text = ugettext_noop("All Categories")

    @property
    def options(self):
        if hasattr(Domain, 'categories'):
            available_categories = [(d.replace(' ', '+'), d) for d in Domain.categories()]
        else:
            available_categories = []
        return available_categories


class SelectOrganizationFilter(BaseSingleOptionFilter):
    slug = "org"
    label = ugettext_noop("Organization")
    default_text = ugettext_noop("All Organizations")

    @property
    def options(self):
        return [(o.name, o.title) for o in  Organization.get_all()]


class GroupFilterMixin(object):
    slug = "group"
    label = ugettext_noop("Group")

    @property
    def options(self):
        return [(group.get_id, group.name) for group in Group.get_reporting_groups(self.domain)]


class GroupFilter(GroupFilterMixin, BaseSingleOptionFilter):
    default_text = ugettext_noop("Everybody")


class MultiSelectGroupTypeaheadFilter(GroupFilterMixin, BaseMultipleOptionTypeaheadFilter):
    default_options = ['_all']
    help_text = "Start typing to select one or more groups"


class YearFilter(BaseSingleOptionFilter):
    slug = "year"
    label = ugettext_noop("Year")
    default_text = None

    @property
    def options(self):
        start_year = getattr(settings, 'START_YEAR', 2008)
        years = [(y, y) for y in range(start_year, datetime.datetime.utcnow().year + 1)]
        years.reverse()
        return years


class MonthFilter(BaseSingleOptionFilter):
    slug = "month"
    label = ugettext_noop("Month")
    default_text = None

    @property
    def options(self):
        return [("%02d" % m, calendar.month_name[m]) for m in range(1, 13)]


class CaseTypeFilter(BaseSingleOptionFilter):
    slug = "case_type"
    label = ugettext_noop("Case Type")
    default_text = ugettext_noop("All Case Types")

    @property
    def options(self):
        case_types = self.get_case_types(self.domain)
        return [(case, "%s" % case) for case in case_types]

    @classmethod
    def get_case_types(cls, domain):
        key = [domain]
        for r in CommCareCase.get_db().view(
                'hqcase/all_cases',
                startkey=key,
                endkey=key + [{}],
                group_level=2
            ).all():
            _, case_type = r['key']
            if case_type:
                yield case_type

    @classmethod
    def get_case_counts(cls, domain, case_type=None, user_ids=None):
        """
        Returns open count, all count
        """
        user_ids = user_ids or [{}]
        for view_name in ('hqcase/open_cases', 'hqcase/all_cases'):
            def individual_counts():
                for user_id in user_ids:
                    key = [domain, case_type or {}, user_id]
                    try:
                        yield CommCareCase.get_db().view(
                            view_name,
                            startkey=key,
                            endkey=key + [{}],
                            group_level=0
                        ).one()['value']
                    except TypeError:
                        yield 0
            yield sum(individual_counts())


class SelectOpenCloseFilter(BaseSingleOptionFilter):
    slug = "is_open"
    label = ugettext_noop("Opened / Closed")
    default_text = ugettext_noop("Show All")

    @property
    def options(self):
        return [
            ('open', _("Only Open")),
            ('closed', _("Only Closed")),
        ]


class SelectApplicationFilter(BaseSingleOptionFilter):
    slug = "app"
    label = ugettext_noop("Application")
    default_text = ugettext_noop("Select Application [Latest Build Version]")

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


class UserOrGroupFilter(BaseSingleOptionFilter):
    """
        To Use: Subclass and specify what the field options should be
    """
    slug = "view_by"
    label = ugettext_noop("View by Users or Groups")
    default_text = ugettext_noop("Users")
    options = [
        ('groups', 'Groups'),
    ]
