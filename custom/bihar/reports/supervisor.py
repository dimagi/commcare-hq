from copy import copy
import urllib
from datetime import datetime, timedelta
from corehq.util.spreadsheets.excel import alphanumeric_sort_key
from dimagi.utils.couch.database import iter_docs

from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain_by_owner
from corehq.util.soft_assert import soft_assert
from custom.bihar.utils import (get_team_members, get_all_owner_ids_from_group, SUPERVISOR_ROLES, FLW_ROLES,
    groups_for_user, get_role)

from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport,\
    SummaryTablularReport, summary_context
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
from dimagi.utils.html import format_html
from corehq.apps.groups.models import Group
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.case.models import CommCareCase
from custom.bihar.reports.indicators.mixins import IndicatorConfigMixIn


def shared_bihar_context(report):
    return {
        'home':      MainNavReport.get_url(report.domain, render_as=report.render_next),
        'render_as': report.render_next,
        'mode': report.mode,
    }


class ConvenientBaseMixIn(object):
    # this is everything that's shared amongst the Bihar supervision reports
    # this class is an amalgamation of random behavior and is just 
    # for convenience

    base_template_mobile = "bihar/base_template_mobile.html"
    report_template_path = "reports/async/tabular.html"

    hide_filters = True
    flush_layout = True
    mobile_enabled = True
    fields = []

    extra_context_providers = [shared_bihar_context]

    # for the lazy
    _headers = []  # override
    @property
    def headers(self):
        headers = self._headers[self.mode] if isinstance(self._headers, dict) else self._headers
        return DataTablesHeader(*(DataTablesColumn(_(h)) for h in headers))

    @property
    def render_next(self):
        return None if self.rendered_as == "async" else self.rendered_as

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return False

    @property
    @memoized
    def mode(self):
        # sup_roles = ('ANM', 'LS') # todo if we care about these
        man_roles = ('MOIC', 'BHM', 'BCM', 'CDPO')
        if self.request.couch_user.is_commcare_user():
            if get_role(self.request.couch_user) in man_roles:
                return 'manager'
        return 'supervisor'

    @property
    def is_supervisor(self):
        return self.mode == 'supervisor'

    @property
    def is_manager(self):
        return self.mode == 'manager'


def list_prompt(index, value):
    # e.g. 1. Reports
    return u"%s. %s" % (_(str(index+1)), _(value))


class ReportReferenceMixIn(object):
    # allow a report to reference another report

    @property
    def next_report_slug(self):
        return self.request_params.get("next_report")

    @property
    def next_report_class(self):
        return CustomProjectReportDispatcher().get_report(self.domain, self.next_report_slug)


class GroupReferenceMixIn(object):
    # allow a report to reference a group

    @property
    def group_id(self):
        return self.request_params["group"]

    @property
    @memoized
    def group(self):
        g = Group.get(self.group_id)
        assert g.domain == self.domain, "Group %s isn't in domain %s" % (g.get_id, self.domain)
        return g

    @memoized
    def get_team_members(self):
        """
        Get any commcare users that are either "asha" or "aww".
        """
        roles = {
            'supervisor': FLW_ROLES,
            'manager': SUPERVISOR_ROLES,
        }
        return get_team_members(self.group, roles=roles[self.mode])

    @property
    @memoized
    def all_owner_ids(self):
        return get_all_owner_ids_from_group(self.group)

    @property
    @memoized
    def cases(self):
        _assert = soft_assert('@'.join(['droberts', 'dimagi.com']))
        _assert(False, "I'm surprised GroupReferenceMixIn ever gets called!")
        case_ids = get_case_ids_in_domain_by_owner(
            self.domain, owner_id__in=self.all_owner_ids, closed=False)
        # really inefficient, but can't find where it's called
        # and this is what it was doing before
        return [CommCareCase.wrap(doc)
                for doc in iter_docs(CommCareCase.get_db(), case_ids)]

    @property
    @memoized
    def group_display(self):
        return {
            'supervisor': u'{group} ({awcc})',
            'manager': u'{group}',
        }[self.mode].format(group=self.group.name, awcc=get_awcc(self.group))

    @property
    def rendered_report_title(self):
        return u"{title} - {group}".format(title=_(self.name),
                                           group=self.group_display)


def team_member_context(report):
    """
    Gets context for adding a team members listing to a report.
    """
    return {
        "team_members": report.get_team_members(),
    }


class BiharSummaryReport(ConvenientBaseMixIn, SummaryTablularReport,
                         CustomProjectReport):
    # this is literally just a way to do a multiple inheritance without having
    # the same 3 classes extended by a bunch of other classes
    base_template_mobile = "bihar/bihar_summary.html"
    report_template_path = "reports/async/summary_tabular.html"
    extra_context_providers = [shared_bihar_context, summary_context]


class BiharNavReport(BiharSummaryReport):
    # this is a bit of a bastardization of the summary report
    # but it is quite DRY

    preserve_url_params = False

    @property
    def reports(self):
        # override
        raise NotImplementedError("Override this!")

    @property
    def _headers(self):
        return [" "] * len(self.reports)

    @property
    def data(self):
        return [default_nav_link(self, i, report_cls) for i, report_cls in enumerate(self.reports)]


class MockEmptyReport(BiharSummaryReport):
    """
    A stub empty report
    """
    _headers = ["Whoops, this report isn't done! Sorry this is still a prototype."]
    data = [""]


class SubCenterSelectionReport(ConvenientBaseMixIn, GenericTabularReport,
                               CustomProjectReport, ReportReferenceMixIn):
    name = ugettext_noop("Select Subcenter")
    slug = "subcenter"
    description = ugettext_noop("Subcenter selection report")

    _headers = {
        'supervisor': [ugettext_noop("Team Name"), ugettext_noop("AWCC")],
        'manager': [ugettext_noop("Subcentre")],
    }

    @memoized
    def _get_groups(self):
        groups = groups_for_user(self.request.couch_user, self.domain)
        return sorted(
            groups,
            key=lambda group: alphanumeric_sort_key(group.name)
        )

    @property
    def rows(self):
        return [self._row(g, i+1) for i, g in enumerate(self._get_groups())]

    def _row(self, group, rank):

        def _link(g, text):
            params = copy(self.request_params)
            params["group"] = g.get_id
            return format_html(u'<a href="{details}">{text}</a>',
                text=text,
                details=url_and_params(self.next_report_class.get_url(domain=self.domain,
                                                                      render_as=self.render_next),
                                       params))


        return [group.name, _link(group, get_awcc(group))] if self.is_supervisor else [_link(group, group.name)]


class MainNavReport(BiharSummaryReport, IndicatorConfigMixIn):
    name = ugettext_noop("Main Menu")
    slug = "mainnav"
    description = ugettext_noop("Main navigation")

    @classmethod
    def additional_reports(cls):
        from custom.bihar.reports.due_list import DueListSelectionReport
        from custom.bihar.reports.indicators.reports import MyPerformanceReport
        return [DueListSelectionReport, ToolsNavReport, MyPerformanceReport]

    @classmethod
    def show_in_navigation(cls, *args, **kwargs):
        return True

    @property
    def _headers(self):
        return [" "] * (len(self.indicator_config.indicator_sets) + len(self.additional_reports()))

    @property
    def data(self):
        from custom.bihar.reports.indicators.reports import IndicatorNav

        def _indicator_nav_link(i, indicator_set):
            params = copy(self.request_params)
            params["indicators"] = indicator_set.slug
            params["next_report"] = IndicatorNav.slug
            return format_html(u'<a href="{next}">{val}</a>',
                val=list_prompt(i, indicator_set.name),
                next=url_and_params(
                    SubCenterSelectionReport.get_url(self.domain,
                                                     render_as=self.render_next),
                    params
            ))
        return [_indicator_nav_link(i, iset) for i, iset in\
                enumerate(self.indicator_config.indicator_sets)] + \
               [default_nav_link(self, len(self.indicator_config.indicator_sets) + i, r) \
                for i, r in enumerate(self.additional_reports())]


class ToolsNavReport(BiharSummaryReport):
    name = ugettext_noop("Tools Menu")
    slug = "tools"

    _headers = [" ", " ", " "]

    @property
    def data(self):
        def _referral_link(i):
            params = copy(self.request_params)
            params["next_report"] = ReferralListReport.slug
            return format_html(u'<a href="{next}">{val}</a>',
                val=list_prompt(i, _(ReferralListReport.name)),
                next=url_and_params(
                    SubCenterSelectionReport.get_url(self.domain,
                                                     render_as=self.render_next),
                    params
            ))
        return [_referral_link(0),
                default_nav_link(self, 1, EDDCalcReport),
                default_nav_link(self, 2, BMICalcReport),]


class ReferralListReport(GroupReferenceMixIn, MockEmptyReport):
    name = ugettext_noop("Referrals")
    slug = "referrals"

    _headers = []

    @property
    def data(self): # this is being called multiple times

        def render(f):
            title = {
                "public": _("Public Facility"),
                "private": _("Private Facility"),
                "transport": _("Transport")
            }[f.fields_without_attributes["type"]]
            return format_html(u"%s: %s<br /># %s" % (title, f.fields_without_attributes.get("name", ""), f.fields_without_attributes.get("number", "")))

        fixtures = FixtureDataItem.by_group(self.group)
        _data = []
        self._headers = []
        for f in fixtures:
            _data.append(render(f))
            self._headers.append(" ")

        if not _data:
            _data = ['No referrals for %s' % self.group.name]
            self._headers = [" "]
        return _data


class InputReport(MockEmptyReport):
    name = ""
    slug = ""
    _headers = [" "]
    _inputs = []

    @property
    def form_html(self):
        return render_to_string("bihar/partials/input.html", {"inputs": self._inputs})

    @property
    def data(self):
        for i in self._inputs:
            if not self.request.GET.get(i["name"], None):
                return [self.form_html]
        return self.calc(self.request.GET)

    def calc(self, input):
        return [_("This calculation has not yet been implemented.")]


class EDDCalcReport(InputReport):
    name = ugettext_noop("EDD Calculator")
    slug = "eddcalc"
    _inputs = [
        {
            "name": "lmp",
            "type": "text",
            "label": ugettext_noop("Enter LMP (DD-MM-YYYY)")
        }
    ]

    _headers = [" "]

    def calc(self, input):
        try:
            lmp_date = datetime.strptime(input["lmp"], "%d-%m-%Y")
            edd_date = lmp_date + timedelta(days=280)
            return [_("Estimated Date of Delivery: %s") % edd_date.strftime("%d-%m-%Y")]
        except ValueError:
            self._headers = [" ", " "]
            return [_("Error: We can't parse your input, please try again"), self.form_html]


class BMICalcReport(InputReport):
    name = ugettext_noop("BMI Calculator")
    slug = "bmicalc"
    _inputs = [
        {
            "name": "weight",
            "type": "text",
            "label": ugettext_noop("Enter weight in kilograms:")
        },
        {
            "name": "height",
            "type": "text",
            "label": ugettext_noop("Enter height in meters:")
        }
    ]

    def calc(self, input):
        try:
            weight = float(input["weight"])
            height = float(input["height"])
        except ValueError:
            self._headers = [" ", " "]
            return [_("Error: We can't parse your input, please try again"), self.form_html]

        bmi = weight / (height * height)
        if bmi >= 30:
            return [_("You are obese")]
        elif bmi >= 25:
            return [_("You are overweight")]
        elif bmi >= 18.5:
            return [_("You are normal weight")]
        else:
            return [_("You are underweight")]


def default_nav_link(nav_report, i, report_cls):
    url = report_cls.get_url(nav_report.domain,
                             render_as=nav_report.render_next)
    if getattr(nav_report, 'preserve_url_params', False):
        url = url_and_params(url, nav_report.request_params)
    return format_html(u'<a href="{details}">{val}</a>',
                        val=list_prompt(i, report_cls.name),
                        details=url)


def get_awcc(group):
    return group.metadata.get("awc-code") or _('no awcc')


def url_and_params(urlbase, params):
    assert "?" not in urlbase
    return "{url}?{params}".format(url=urlbase,
                                   params=urllib.urlencode(params))
