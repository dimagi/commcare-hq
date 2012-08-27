from corehq.apps.reports._global import CustomProjectReport
from corehq.apps.reports.fields import ReportField
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from functools import wraps
from dateutil.parser import parse, tz

class ProjectOfficerReport(GenericTabularReport, CustomProjectReport):
    """
        Legacy Custom Report
        This custom report is not structured well.
        Don't look at this report for best practices. (Check out HSPH reports or something newer)
    """
    name = "Project Officer Portfolio"
    slug = "officer_portfolio"
    fields = ['corehq.apps.reports.fields.MonthField',
              'corehq.apps.reports.fields.YearField',
              'dca.reports.OfficerSelectionField']
    exportable = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name of Group"),
            DataTablesColumn("Group #"),
            DataTablesColumn("Linkage to external savings"),
            DataTablesColumn("Linkage to external credit"),
            DataTablesColumn("Date of first training meeting"),
            DataTablesColumn("Date savings started this cycle"),
            DataTablesColumn("Group trained by"),
            DataTablesColumn("Members at start of cycle"),
            DataTablesColumn("Date of data collection"),
            DataTablesColumn("Registered members at present"),
            DataTablesColumn("Registered men at present"),
            DataTablesColumn("Registered women at present"),
            DataTablesColumn("No. of members attending meeting"),
            DataTablesColumn("Dropouts this cycle"),
            DataTablesColumn("Value of savings this cycle"),
            DataTablesColumn("No. of loans outstanding"),
            DataTablesColumn("Value of loans outstanding"),
            DataTablesColumn("Unpaid balance of late loans"),
            DataTablesColumn("Write-offs this cycle"),
            DataTablesColumn("Loan fund cash in box/bank"),
            DataTablesColumn("Cash in other funds"),
            DataTablesColumn("Property at start of cycle"),
            DataTablesColumn("Property now"),
            DataTablesColumn("Debts"),
            DataTablesColumn("Interest rate")
        )

    @property
    def rows(self):
        officer = self.request.GET.get("officer", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (officer and month and year):
            return []

        results = get_db().view('dca/dca_collection_forms', key=[officer, int(month), int(year)], include_docs=True).all()

        selectors = [
            "group_name",
            "group_number",
            "linkage_to_external_savings",
            "linkage_to_external_credit",
            "date_of_first_training",
            "date_savings_started_this_cycle",
            "",#group_trained_by",
            "members_at_start_of_cycle",
            "date_of_data_collection",
            "active_members_at_time_of_visit",
            "active_men_at_time_of_visit",
            "active_women_at_time_of_visit",
            "no_of_members_attending_meeting",
            "dropouts_since_start_of_cycle",
            "value_of_savings_this_cycle",
            "no_of_loans_outstanding",
            "value_of_loans_outstanding",
            "unpaid_balance_of_late_loans",
            "write_off_since_start_of_cycle",
            "loan_fund_cash_in_box_at_bank",
            "cash_in_other_funds",
            "property_at_start_of_cycle",
            "property_now",
            "debts",
            "interest_rate"
        ]

        rows = []
        for result in results:
            row = []
            for s in selectors:
                if s in result['doc']['form']:
                    row.append(result['doc']['form'][s])
                else:
                    row.append('-')

            rows.append(row)

        return rows

class OfficerSelectionField(ReportField):
    slug = "officer"
    template = "dca/officer-select.html"
    def update_context(self):
        results = get_db().view('dca/dca_collection_forms').all()
        res = set([result['key'][0] for result in results])
        self.context['officers'] = res
        self.context['officer'] = self.request.GET.get('officer', None)

class CurrencySelectionField(ReportField):
    slug = "currency"
    template = "dca/curselect.html"
    def update_context(self):
        self.context['curname'] =  self.request.GET.get('curname', "MK")
        self.context['curval'] = self.request.GET.get('curval', 1.0)

class LendingGroup(object):
    case = None
    coll = None

    def __init__(self, case, month, year):
        self.case = case
        startkey = [self.case['_id'], int(year), int(month)]
        endkey=[self.case['_id'], int(year), int(month), {}]
        tmp = get_db().view('dca/dca_collection_forms_by_case', startkey=startkey,
            endkey=endkey, include_docs=True, limit=1).all()
        if len(tmp):
            self.coll = tmp[0]

    def __getattr__(self, item):
        """
        Check the collection (will have data from the relevant month) and fall back to the case if the info isn't
        there.
        """
        try:
            return self.coll['doc']['form'][item]
        except Exception:
            try:
                return self.coll[item]
            except Exception:
                try:
                    return self.case[item]
                except Exception:
                    try:
                        return self.case['_doc'][item]
                    except Exception:
                        return None
                        # raise AttributeError("Couldn't find %s in either the collection or the case." % item)


def _group_age(x):
    y = parse(x.opened_on)
    z = parse(x.date_savings_started_this_cycle)
    a = y - z.replace(tzinfo=tz.tzutc())
    return a.days

def _member_delta(x):
    try:
        return int(x.active_members_at_time_of_visit) - int(x.members_at_start_of_cycle)
    except (ValueError, TypeError):
        return 0.0

class LendingGroupAggregate(object):
    """
    Utility class to hold data for a group of lending groups, such as those supervised by an officer.
    """
    name = ""
    users = []
    number = ""
    groups = []

    def __init__(self, name, user_ids, month, year, curval, curname):
        self.name = name
        self.curval = curval
        self.curname = curname
        users = [CommCareUser.get(user_id) for user_id in user_ids]
        groups = []
        for user in users:
            tmp = get_db().view('case/by_owner', key=[user._id, False], include_docs=True, reduce=False).all()
            for t in tmp:
                groups.append(LendingGroup(CommCareCase.get(t['doc']['_id']), month, year))
        self.groups = groups if groups else []

    def _all(self, l, flt=None):
        if flt:
            return map(l, filter(flt, self.groups))
        return filter(lambda x: x is not None, map(l, self.groups))

    # Utility functions
    def sum_all_groups(self, l):
        intr = self._all(l)
        res = map(lambda x: float(x) if x else 0.0, intr)
        r = sum(res)
        return r

    def avg_all_groups(self, l):
        if not len(self.groups): return None
        return self.sum_all_groups(l)/float(len(self.groups))

    def currency(self, a): return "%s%.2f" % (self.curname, self.curval * float(a)) if a else "n/a"

    def div(self, a, b): return a/b if b else 0.0

    def pct(self, a, b):
        try:
            return "%.1f%%" % (100.0 * (self.div(a, b)))
        except TypeError:
            return "n/a"

    def __getattr__(self, item):
        if not item:
            raise AttributeError
        if item.startswith('cur__'):
            return self.currency(self.__getattr__(item[5:]))
        elif item.startswith('avg__'):
            return self.avg_all_groups(lambda x: float(x.__getattr__(item[5:])))
        elif item.startswith('sum__'):
            return self.sum_all_groups(lambda x: int(x.__getattr__(item[5:])))

    # Columns
    @property
    def num_groups(self):
        return len(self.groups)

    @property
    def num_members(self):
        return self.sum_all_groups(lambda x: x.active_members_at_time_of_visit)

    @property
    def avg_members(self):
        return self.avg_all_groups(lambda x: x.active_members_at_time_of_visit)

    @property
    def num_men(self):
        return self.sum_all_groups(lambda x: x.active_men_at_time_of_visit)

    @property
    def avg_men(self):
        return self.avg_all_groups(lambda x: x.active_men_at_time_of_visit)

    @property
    def num_women(self):
        return self.sum_all_groups(lambda x: x.active_women_at_time_of_visit)

    @property
    def avg_women(self):
        return self.avg_all_groups(lambda x: x.active_women_at_time_of_visit)

    @property
    def members_at_start_of_cycle(self):
        return self.sum_all_groups(lambda x: x.members_at_start_of_cycle)

    @property
    def avg_members_at_start_of_cycle(self):
        return self.sum_all_groups(lambda x: x.members_at_start_of_cycle)

    @property
    def num_women(self):
        return self.sum_all_groups(lambda x: x.active_women_at_time_of_visit)

    @property
    def pct_women(self):
        return self.pct(self.num_women, self.num_members)

    @property
    def loans_outstanding(self):
        return self.sum_all_groups(lambda x: x.no_of_loans_outstanding)

    @property
    def avg_loans_outstanding(self):
        return self.avg_all_groups(lambda x: x.no_of_loans_outstanding)


    @property
    def _value_of_loans_outstanding(self):
        return self.sum_all_groups(lambda x: x.value_of_loans_outstanding)

    @property
    def value_of_loans_outstanding(self):
        return self.currency(self._value_of_loans_outstanding)

    @property
    def avg_value_of_loans_outstanding(self):
        return self.currency(self.div(self._value_of_loans_outstanding, self.num_groups))

    @property
    def pct_loans_outstanding(self):
        return self.pct(self.loans_outstanding, self.num_members)

    @property
    def _avg_outstanding_loan_size(self):
        return self.div(self._value_of_loans_outstanding, self.loans_outstanding)

    @property
    def avg_outstanding_loan_size(self):
        return self.currency(self._avg_outstanding_loan_size)

    @property
    def _unpaid_balance_of_late_loans(self):
        return self.sum_all_groups(lambda x: x.unpaid_balance_of_late_loans)

    @property
    def unpaid_balance_of_late_loans(self):
        return self.currency(self._unpaid_balance_of_late_loans)

    @property
    def pct_portfolio_at_risk(self):
        return self.pct(self._unpaid_balance_of_late_loans, self._value_of_loans_outstanding)

    @property
    def members_attending(self):
        return self.sum_all_groups(lambda x: x.no_of_members_attending_meeting)

    @property
    def attendance_rate(self):
        return self.pct(self.members_attending, self.num_members)

    @property
    def dropouts_since_start_of_cycle(self):
        return self.sum_all_groups(lambda x: x.dropouts_since_start_of_cycle)

    @property
    def dropout_rate(self):
        return self.pct(self.dropouts_since_start_of_cycle, self.num_members)

    @property
    def retention_rate(self):
        if self.num_members:
            return self.pct(self.num_members - self.dropouts_since_start_of_cycle, self.num_members)
        else:
            return None

    @property
    def change_in_members(self):
        return self.sum_all_groups(_member_delta)

    @property
    def avg_change_in_members(self):
        return self.avg_all_groups(_member_delta)

    def pct_change_in_members(self):
        return self.pct(self.change_in_members, self.members_at_start_of_cycle)

    @property
    def _value_of_savings(self):
        return self.sum_all_groups(lambda x: x.value_of_savings_this_cycle)

    @property
    def value_of_savings(self):
        return self.currency(self._value_of_savings)

    @property
    def value_of_savings_per_member(self):
        return self.currency(self.div(self._value_of_savings, self.num_members))

    @property
    def avg_value_of_savings(self):
        return self.currency(self.avg_all_groups(lambda x: x.value_of_savings_this_cycle))

    @property
    def _loan_fund_cash_in_box_at_bank(self):
        return self.sum_all_groups(lambda x: x.loan_fund_cash_in_box_at_bank)

    @property
    def loan_fund_cash_in_box_at_bank(self):
        return self.currency(self._loan_fund_cash_in_box_at_bank)

    @property
    def avg_loan_fund_cash_in_box_at_bank(self):
        return self.currency(self.div(self._loan_fund_cash_in_box_at_bank, self.num_groups))

    @property
    def loan_fund_utilization(self):
        return self.pct(self._value_of_loans_outstanding, self._value_of_loans_outstanding + self._loan_fund_cash_in_box_at_bank)

    @property
    def avg_age_of_group(self):
        return round(self.sum_all_groups(_group_age) / 7.0, 2)

    @property
    def average_age(self):
        return self.div(self._age_of_groups_in_weeks, self.num_groups)

    @property
    def _debts(self):
        return self.sum_all_groups(lambda x: x.debts)

    @property
    def debts(self):
        return self.currency(self._debts)

    @property
    def avg_debts(self):
        return self.currency(self.avg_all_groups(lambda x: x.debts))

    @property
    def pct_debts_liabilities(self):
        return self.pct(self._debts, self._liabilities_and_equity)

    @property
    def _cash_in_other_funds(self):
        return self.sum_all_groups(lambda x: x.cash_in_other_funds)

    @property
    def cash_in_other_funds(self):
        return self.currency(self._cash_in_other_funds)

    @property
    def avg_cash_in_other_funds(self):
        return self.currency(self.avg_all_groups(lambda x:x.cash_in_other_funds))

    @property
    def property_now(self):
        return self.currency(self._property_now)

    @property
    def _property_now(self):
        return self.sum_all_groups(lambda x: x.property_now)

    @property
    def avg_property_now(self):
        return self.currency(self.div(self._property_now, self.num_groups))

    @property
    def _property_at_start_of_cycle(self):
        return self.sum_all_groups(lambda x: x.property_at_start_of_cycle)

    @property
    def property_at_start_of_cycle(self):
        return self.sum_all_groups(lambda x: x.property_at_start_of_cycle)

    @property
    def avg_property_at_start_of_cycle(self):
        return self.currency(self.div(self._property_at_start_of_cycle, self.num_groups))

    @property
    def _assets(self):
        try:
            return self._loan_fund_cash_in_box_at_bank + self._value_of_loans_outstanding + self._cash_in_other_funds + self._property_now
        except:
            return 0

    @property
    def pct_loans_assets(self):
        return self.pct(self._value_of_loans_outstanding, self._assets)

    @property
    def pct_loan_fund_cash_assets(self):
        return self.pct(self._loan_fund_cash_in_box_at_bank, self._assets)

    @property
    def pct_cash_assets(self):
        return self.pct(self._cash_in_other_funds, self._assets)

    @property
    def pct_property_assets(self):
        return self.pct(self._property_now, self._assets)

    @property
    def assets(self):
        return self.currency(self._assets)

    @property
    def avg_assets(self):
        return self.currency(self.div(self._assets, self.num_groups))

    @property
    def _equity(self):
        return self._cash_in_other_funds + self._value_of_savings + self._retained_earnings

    @property
    def avg_equity_per_member(self):
        return self.currency(self.div(self._equity, self.num_members))

    @property
    def _liabilities_and_equity(self):
        return self._debts +self._equity

    @property
    def liabilities_and_equity(self):
        return self.currency(self._liabilities_and_equity)

    @property
    def avg_liabilities_and_equity(self):
        return self.currency(self.div(self._liabilities_and_equity, self.num_groups))

    @property
    def pct_debts_liabilities(self):
        return self.pct(self._debts, self._liabilities_and_equity)

    @property
    def pct_cash_liabilities(self):
        return self.pct(self._cash_in_other_funds, self._liabilities_and_equity)

    @property
    def pct_savings_liabilities(self):
        return self.pct(self._value_of_savings, self._liabilities_and_equity)

    @property
    def pct_earnings_liabilities(self):
        return self.pct(self._retained_earnings, self._liabilities_and_equity)


    @property
    def _writeoffs(self):
        return self.sum_all_groups(lambda x: x.write_off_since_start_of_cycle)

    @property
    def writeoffs(self):
        return self.currency(self._writeoffs)

    @property
    def avg_writeoffs(self):
        return self.currency(self.avg_all_groups(lambda x: x.write_off_since_start_of_cycle))

    @property
    def _profits(self):
        return self._loan_fund_cash_in_box_at_bank \
               - self._value_of_savings \
               - self._property_at_start_of_cycle \
               + self._value_of_loans_outstanding \
               + self._property_now \
               - self._debts

    @property
    def profits(self):
        return self.currency(self._profits)

    @property
    def avg_profits_per_group(self):
        return self.currency(self.div(self._profits, self.num_groups))

    @property
    def avg_profits_per_member(self):
        return self.currency(self.div(self._profits, self.num_members))

    @property
    def _retained_earnings(self):
        return self._profits + self._property_at_start_of_cycle

    @property
    def retained_earnings(self):
        return self.currency(self._retained_earnings)

    @property
    def avg_retained_earnings(self):
        return self.currency(self.div(self._retained_earnings, self.num_groups))

    @property
    def one_hundred_percent(self):
        return self.pct(1.0,1.0)


class PortfolioComparisonReport(GenericTabularReport, CustomProjectReport):
    """
        Legacy Custom Report
        This custom report is not structured well.
        Don't look at this report for best practices. (Check out HSPH reports or something newer)
    """
    name = "Portfolio Comparison"
    slug = "portfolio_comparison"
    fields = ['corehq.apps.reports.fields.MonthField',
              'corehq.apps.reports.fields.YearField',
              'corehq.apps.reports.fields.GroupField',
              'dca.reports.CurrencySelectionField']
    exportable = True

    columns = [
        ('Name of Project Officer', "name"),
        ('No. of Project Officer', 'number'),
        ('Total number of supervised groups', 'num_groups'),
        ('Registered members', 'num_members'),
        ('Change in number of members this cycle', 'change_in_members'),
        ('Dropout rate', 'dropout_rate'),
        ('Attendance rate', 'attendance_rate'),
        ('% of women', 'pct_women'),
        ('Members with loans outstanding', 'loans_outstanding'),
        ('Average outstanding loan size', 'avg_outstanding_loan_size'),
        ('Unpaid balance of late loans', 'unpaid_balance_of_late_loans'),
        ('Portfolio at risk (%)', 'pct_portfolio_at_risk'),
        ('Value of savings', 'value_of_savings'),
        ('Loan fund utilisation rate (%)', 'loan_fund_utilization'), # utilisation [sic]
        ('Return on savings', None),
        ('Return on assets', None),
        ('Annualized return on assets', None),
    ]

    @property
    def headers(self):
        headers = map(lambda x: x[0], self.columns)
        dt_header = DataTablesHeader()
        for header in headers:
            dt_header.add_column(DataTablesColumn(header))
        return dt_header

    @property
    def report_context(self):
        context = super(PortfolioComparisonReport, self).report_context
        context.update(
            curval=float(self.request.GET.get("curval", 1.0)),
            curname=self.request.GET.get("curname", "MK")
        )
        return context

    @property
    def rows(self):
        group_id = self.request.GET.get("group", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        curval = float(self.request.GET.get("curval", 1.0))
        curname = self.request.GET.get("curname", "MK")

        if not (month and year):
            return []

        rows = []
        if group_id:
            group = Group.get(group_id)
            users = group.users
        else:
            users = CommCareUser.by_domain(self.domain)

        for user in users:
            row = []
            lg = LendingGroupAggregate(user.full_name, [user._id], month, year, curval, curname)
            for v in self.columns:
                try:
                    if v[1]:
                        row.append(getattr(lg, v[1]))
                    else:
                        row.append('-')
                except TypeError:
                    row.append('-')
            rows.append(row)

        return rows

class PerformanceReport(GenericTabularReport, CustomProjectReport):
    """
        Legacy Custom Report
        This custom report is not structured well.
        Don't look at this report for best practices. (Check out HSPH reports or something newer)
    """
    name = "Project Performance"
    slug = "project_performance"
    exportable = True
    use_datatables = False
    fields = ['corehq.apps.reports.fields.MonthField',
              'corehq.apps.reports.fields.YearField',
              'corehq.apps.reports.fields.GroupField',
              'dca.reports.CurrencySelectionField']


    # Aggregate, %, Avg
    _rows = [
        ('<h2>Group Profile</h2>','','',''),
        ('Number of groups', 'num_groups', '', ''),
        ('Total number of current members', 'num_members', '', 'avg_members'),
        ('Total men', 'num_men', '', 'avg_women'),
        ('Total women', 'num_women', '', 'avg_women'),
        ('Total number of supervised groups', 'num_groups', '', ''),
        ('Total number of graduated groups', '', '', ''),
        ('Average age of group (weeks)', '','','avg_age_of_group'),
        ('Membership growth rate', 'change_in_members','pct_change_in_members','avg_change_in_members'),
        ('Attendance rate', '','attendance_rate',''),
        ('Retention rate', '', 'retention_rate',''),
        ('Number of members belonging to graduated groups', '','',''),
        ('Total number of people assisted by the program', '','',''),
        ('Percent of members with loans outstanding', '', 'pct_loans_outstanding', ''),
        ('','','',''),
        ('<h2>Financial Performance of Groups</h2>','','',''),
        ('<h3>Composition of assets, liabilities, and equity</h3>','','',''),
        ('<b>Assets</b>', 'assets', 'one_hundred_percent', 'avg_assets'),
        ('Loan fund cash on hand', 'loan_fund_cash_in_box_at_bank', 'pct_loan_fund_cash_assets', 'avg_loan_fund_cash_in_box_at_bank'),
        ('Total cash in other funds', 'cash_in_other_funds', 'pct_cash_assets', 'avg_cash_in_other_funds'),
        ('Value of loans outstanding', 'value_of_loans_outstanding', 'pct_loans_assets', 'avg_value_of_loans_outstanding'),
        ('Property', 'property_now', 'pct_property_assets', 'avg_property_now'),
        #------------
        ('<b>Total liabilities and equity</b>', 'liabilities_and_equity', 'one_hundred_percent', 'avg_liabilities_and_equity'),
        ('Debts', 'debts', 'pct_debts_liabilities', 'avg_debts'),
        ('Cash in other funds', 'cash_in_other_funds', 'pct_cash_liabilities', 'avg_cash_in_other_funds'),
        ('Savings', 'value_of_savings', 'pct_savings_liabilities', 'avg_value_of_savings'),
        ('Retained earnings', 'retained_earnings', 'pct_earnings_liabilities', 'avg_retained_earnings'),
        ('','','',''),
        #------------
        ('<h3>Savings</h3>','','',''),
        ('Cumulative value of savings this cycle', 'value_of_savings','','avg_value_of_savings'),
        ('Average savings per member', '','','value_of_savings_per_member'),
        ('Retained earnings', 'retained_earnings', '', ''),
        ('Average member equity', '','','avg_equity_per_member'),
        ('','','',''),
        #------------
        ('<h3>Loan Portfolio</h3>','','',''),
        ('Number of loans outstanding', 'loans_outstanding', '', 'avg_loans_outstanding'),
        ('Value of loans outstanding', 'value_of_loans_outstanding', '', 'avg_value_of_loans_outstanding'),
        ('Average outstanding loan size', '', '', 'avg_outstanding_loan_size'),
        ('Unpaid balance of late loans', 'unpaid_balance_of_late_loans', '', ''),
        ('Portfolio at risk', '', 'pct_portfolio_at_risk', ''),
        ('Average writeoff per graduated group', '', '', 'avg_writeoffs'),
        ('Writeoffs this cycle', 'writeoffs', '', ''),
        ('Loan fund utilisation rate', '', 'loan_fund_utilization', ''),
        ('','','',''),
        ('<h3>Current yield</h3>','','',''),
        ('Average profit per member to date', '','','avg_profits_per_member'),
        ('Return on savings', '','',''),
        ('Return on assets', '','',''),
        ('Annualized return on assets', '','',''),

    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Statistic"),
            DataTablesColumn("Aggregate (All Groups)"),
            DataTablesColumn("%"),
            DataTablesColumn("Average (Per Group)"),
        )

    @property
    def rows(self):
        group_id = self.request.GET.get("group", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        curval = float(self.request.GET.get("curval", 1.0))
        curname = self.request.GET.get("curname", "MK")
        if not (month and year):
            return []


        if group_id:
            group = Group.get(group_id)
            group_name = group.name
            users = group.users
        else:
            users = map(lambda x: x._id, CommCareUser.by_domain(self.domain))
            group_name = "Everybody"

        lg = LendingGroupAggregate(group_name, users, month, year, curval, curname)

        rows = []
        for r in self._rows:
            if r:
                row = [r[0]]
                def _ga(x):
                    if x:
                        r = getattr(lg, x)
                    else:
                        r = ''

                    return r
                row.extend(map(_ga, r[1:]))
                rows.append(row)
            else:
                rows.append(['<hr />'])
        return rows



class PerformanceRatiosReport(GenericTabularReport, CustomProjectReport):
    """
        Legacy Custom Report
        This custom report is not structured well.
        Don't look at this report for best practices. (Check out HSPH reports or something newer)
    """
    name = "Performance Ratios"
    slug = "performance_ratios"
#    template_name = "dca/performance-ratios.html"
    exportable = True
    use_datatables = False
    fields = ['corehq.apps.reports.fields.MonthField',
              'corehq.apps.reports.fields.YearField',
              'corehq.apps.reports.fields.GroupField',
              'dca.reports.CurrencySelectionField']

    _rows = [
        ('Attendance rate','attendance_rate'),
        ('Retention rate','retention_rate'),
        ('Membership growth rate','pct_change_in_members'),
        ('Average savings per member','value_of_savings_per_member'),
        ('Return on assets',''),
        ('Annualized return on assets',''),
        ('Return on savings',''),
        ('Average outstanding loan size','avg_outstanding_loan_size'),
        ('Portfolio at risk','pct_portfolio_at_risk'),
        ('Average write-off per graduated group','avg_writeoffs'),
        ('% of members with loans outstanding','pct_loans_outstanding'),
        ('Loans outstanding as % of total assets','pct_loans_assets'),
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Statistic"),
            DataTablesColumn("Values")
        )

    @property
    def rows(self):
        group_id = self.request.GET.get("group", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        curval = float(self.request.GET.get("curval", 1.0))
        curname = self.request.GET.get("curname", "MK")
        if not (group_id and month and year):
            return []

        if group_id:
            group = Group.get(group_id)
            group_name = group.name
            users = group.users
        else:
            users = map(lambda x: x._id, CommCareUser.by_domain(self.domain))
            group_name = "Everybody"

        lg = LendingGroupAggregate(group_name, users, month, year, curval, curname)

        rows = []
        for r in self._rows:
            if r:
                row = [r[0]]
                def _ga(x):
                    try:
                        if x:
                            return getattr(lg, x)
                        return ''
                    except TypeError:
                        return ''
                row.extend(map(_ga, r[1:]))
                rows.append(row)
            else:
                rows.append(['<hr />'])

        return rows
        