from django.template.loader import render_to_string
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.generic import GenericTabularReport,\
    SummaryTablularReport, summary_context
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from copy import copy
from corehq.apps.reports.dispatcher import CustomProjectReportDispatcher
import urllib
from dimagi.utils.excel import alphanumeric_sort_key
from dimagi.utils.html import format_html
from corehq.apps.groups.models import Group
from dimagi.utils.decorators.memoized import memoized
from casexml.apps.case.models import CommCareCase
from datetime import datetime, timedelta
from corehq.apps.adm.reports.supervisor import SupervisorReportsADMSection

from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from bihar.reports.indicators.mixins import IndicatorConfigMixIn

ASHA_ROLE = 'ASHA'
AWW_ROLE = 'AWW'

def shared_bihar_context(report):
    return {
        'home':      MainNavReport.get_url(report.domain, render_as=report.render_next),
        'render_as': report.render_next
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
        return DataTablesHeader(*(DataTablesColumn(h) for h in self._headers))

    @property
    def render_next(self):
        return None if self.rendered_as == "async" else self.rendered_as
       
    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        return False
     
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
        users = self.group.get_users(only_commcare=True)
        def is_team_member(user):
            role = user.user_data.get('role', '')
            return role == ASHA_ROLE or role == AWW_ROLE

        return sorted([u for u in users if is_team_member(u)], 
                      key=lambda u: u.user_data['role'])

    @property
    @memoized
    def cases(self):
        return CommCareCase.view('case/by_owner', key=[self.group_id, False],
                                 include_docs=True, reduce=False)

    @property
    @memoized
    def rendered_report_title(self):
        return u"{title} - {group} ({awcc})".format(title=_(self.name),
                                           group=self.group.name,
                                           awcc=get_awcc(self.group))

def team_member_context(report):
    """
    Gets context for adding a team members listing to a report.
    """
    return {
        "team_members": report.get_team_members()
    }


class BiharSummaryReport(ConvenientBaseMixIn, SummaryTablularReport, 
                         CustomProjectReport):
    # this is literally just a way to do a multiple inheritance without having
    # the same 3 classes extended by a bunch of other classes
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
    
    _headers = [ugettext_noop("Team Name"), 
                ugettext_noop("AWCC"),
                # ugettext_noop("Rank")
                ]

    @memoized
    def _get_groups(self):
        if self.request.couch_user.is_commcare_user():
            groups = Group.by_user(self.request.couch_user)
        else:
            # for web users just show everything?
            groups = Group.by_domain(self.domain)
        return sorted(
            groups,
            key=lambda group: alphanumeric_sort_key(group.name)
        )
        
    @property
    def rows(self):
        return [self._row(g, i+1) for i, g in enumerate(self._get_groups())]
        
    def _row(self, group, rank):
        
        def _link(g):
            params = copy(self.request_params)
            params["group"] = g.get_id
            return format_html(u'<a href="{details}">{group}</a>',
                group=g.name,
                details=url_and_params(self.next_report_class.get_url(self.domain,
                                                                      render_as=self.render_next),
                                       params))
        return [_link(group), get_awcc(group)]
            

class MainNavReport(BiharSummaryReport, IndicatorConfigMixIn):
    name = ugettext_noop("Main Menu")
    slug = "mainnav"
    description = ugettext_noop("Main navigation")

    @classmethod
    def additional_reports(cls):
        return [WorkerRankSelectionReport, ToolsNavReport]
    
    @classmethod
    def show_in_navigation(cls, request, *args, **kwargs):
        return True

    @property
    def _headers(self):
        return [" "] * (len(self.indicator_config.indicator_sets) + len(self.additional_reports())) 

    @property
    def data(self):
        from bihar.reports.indicators.reports import IndicatorNav

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

    
class WorkerRankSelectionReport(SubCenterSelectionReport):
    slug = "workerranks"
    name = ugettext_noop("Worker Rank Table")
    
    def _row(self, group, rank):
        # HACK: hard code this for now until there's an easier 
        # way to get this from configuration
        args = [self.domain, self.render_next] if self.render_next else [self.domain]
        url = SupervisorReportsADMSection.get_url(*args,
                                                  subreport="worker_rank_table")
        end = datetime.today().date()
        start = end - timedelta(days=30)
        params = {
            "ufilter": 0, 
            "startdate": start.strftime("%Y-%m-%d"),
            "enddate": end.strftime("%Y-%m-%d")
        }
        def _link(g):
            params["group"] = g.get_id
            return format_html(u'<a href="{details}">{group}</a>',
                group=g.name,
                details=url_and_params(url,
                                       params))
        return [_link(group), get_awcc(group)]
    

class DueListReport(MockEmptyReport):
    name = ugettext_noop("Due List")
    slug = "duelist"

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
            }[f.fields["type"]]
            return format_html(u"%s: %s<br /># %s" % (title, f.fields.get("name", ""), f.fields.get("number", "")))

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
            "label": _("Enter LMP (YYYY-MM-DD)")
        }
    ]

    _headers = [" "]

    def calc(self, input):
        try:
            lmp_date = datetime.strptime(input["lmp"], "%Y-%m-%d")
            edd_date = lmp_date + timedelta(days=280)
            return ["Estitmated Date of Delivery: %s" % edd_date.strftime("%Y-%m-%d")]
        except ValueError:
            self._headers = [" ", " "]
            return ["Error: We can't parse your input, please try again", self.form_html]


class BMICalcReport(InputReport):
    name = ugettext_noop("BMI Calculator")
    slug = "bmicalc"
    _inputs = [
        {
            "name": "weight",
            "type": "text",
            "label": _("Enter weight in kilograms:")
        },
        {
            "name": "height",
            "type": "text",
            "label": _("Enter height in meters:")
        }
    ]

    def calc(self, input):
        try:
            weight = float(input["weight"])
            height = float(input["height"])
        except ValueError:
            self._headers = [" ", " "]
            return ["Error: We can't parse your input, please try again", self.form_html]

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
    return group.metadata.get("awc-code", _('no awc code found'))

def url_and_params(urlbase, params):
    assert "?" not in urlbase
    return "{url}?{params}".format(url=urlbase, 
                                   params=urllib.urlencode(params))