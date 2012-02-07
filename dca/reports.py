from corehq.apps.reports.custom import HQReport, ReportField
from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from dateutil.parser import parse, tz

class ProjectOfficerReport(HQReport):
    name = "Project Officer Portfolio"
    slug = "officer_portfolio"
    template_name = "dca/officer-portfolio.html"
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'dca.reports.OfficerSelectionField']
    exportable = True

    def calc(self):
        officer = self.request.GET.get("officer", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (officer and month and year):
            return

        results = get_db().view('dca/dca_collection_forms', key=[officer, int(month), int(year)], include_docs=True).all()

        self.context['headers'] = [
            "Name of Group",
            "Group #",
            "Linkage to external savings",
            "Linkage to external credit",
            "Date of first training meeting",
            "Date savings started this cycle",
            "Group trained by",
            "Members at start of cycle",
            "Date of data collection",
            "Registered members at present",
            "Registered men at present",
            "Registered women at present",
            "No. of members attending meeting",
            "Dropouts this cycle",
            "Value of savings this cycle",
            "No. of loans outstanding",
            "Value of loans outstanding",
            "Unpaid balance of late loans",
            "Write-offs this cycle",
            "Loan fund cash in box/bank",
            "Cash in other funds",
            "Property at start of cycle",
            "Property now",
            "Debts",
            "Interest rate"
        ]

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

        self.context['rows'] = rows

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
        print self.case['_id'], month, year
        startkey = [self.case['_id'], int(year), int(month)]
        endkey=[self.case['_id'], int(year), int(month), {}]
        print startkey, endkey
        tmp = get_db().view('dca/dca_collection_forms_by_case', startkey=startkey,
            endkey=endkey, include_docs=True, limit=1).all()
        print tmp
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
                    raise AttributeError("Couldn't find %s in either the collection or the case.")


def _foo(x):
    y = parse(x.meta['timeEnd'])
    z = parse(x.date_savings_started_this_cycle)
    a = y - z.replace(tzinfo=tz.tzutc())
    return a.days

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
            tmp = get_db().view('case/by_owner', key=[user._id, False], include_docs=True).all()
            for t in tmp:
                groups.append(LendingGroup(CommCareCase.get(t['doc']['_id']), month, year))
        self.groups = groups

    def _all(self, l, flt=None):
        if flt:
            return map(l, filter(flt, self.groups))
        return map(l, self.groups)

    # Utility functions
    def sum_all_groups(self, l):
        return sum(map(lambda x: float(x), self._all(l)))

    def avg_all_groups(self, l):
        if not len(self.groups): return None
        return self.sum_all_groups(l)/float(len(self.groups))

    def currency(self, a): return "%s%.2f" % (self.curname, self.curval * float(a))

    def div(self, a, b): return a/b if b else 0.0

    def pct(self, a, b):
        return "%.1f%%" % (100.0 * (self.div(a, b)))

    def __getattr__(self, item):
        if not item:
            raise AttributeError
        if item.startswith('cur__'):
            return self.currency(self.__getattr__(item[5:]))
        elif item.startswith('avg__'):
            return self.avg_all_groups(lambda x: x.__getattr__(item[5:]))
        elif item.startswith('sum__'):
            return self.sum_all_groups(lambda x: x.__getattr__(item[5:]))

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
    def change_in_members(self):
        return self.sum_all_groups(lambda x: int(x.active_members_at_time_of_visit) - int(x.members_at_start_of_cycle))

    @property
    def avg_change_in_members(self):
        return self.avg_all_groups(lambda x: int(x.active_members_at_time_of_visit) - int(x.members_at_start_of_cycle))

    def pct_change_in_members(self):
        return self.pct(self.change_in_members, self.members_at_start_of_cycle)

    @property
    def _value_of_savings(self):
        return self.sum_all_groups(lambda x: x.value_of_savings_this_cycle)

    @property
    def value_of_savings(self):
        return self.currency(self._value_of_savings)

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
        return round(self.sum_all_groups(_foo) / 7.0, 2)

    @property
    def average_age(self):
        return self.div(self._age_of_groups_in_weeks, self.num_groups)

    @property
    def _debts(self):
        return self.sum_all_groups(lambda x: x.debts)

    @property
    def _cash_in_other_funds(self):
        return self.sum_all_groups(lambda x: x.cash_in_other_funds)

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
    def _assets(self):
        return self._loan_fund_cash_in_box_at_bank + self._value_of_loans_outstanding + self._cash_in_other_funds + self._property_now

    @property
    def assets(self):
        return self.currency(self._assets)

    @property
    def avg_assets(self):
        return self.currency(self.div(self._assets, self.num_groups))

    @property
    def _liabilities_and_equity(self):
        return self._debts + self._cash_in_other_funds + self._value_of_savings

    @property
    def liabilities_and_equity(self):
        return self.currency(self._liabilities_and_equity)

    @property
    def avg_liabilities_and_equity(self):
        return self.currency(self.div(self._liabilities_and_equity, self.num_groups))

class PortfolioComparisonReport(HQReport):
    name = "Portfolio Comparison"
    slug = "portfolio_comparison"
    template_name = "dca/portfolio-comparison.html"
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'corehq.apps.reports.fields.GroupField', 'dca.reports.CurrencySelectionField']
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

    def calc(self):
        group_id = self.request.GET.get("group", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        curval = float(self.request.GET.get("curval", 1.0))
        curname = self.request.GET.get("curname", "MK")

        self.context['curval'] = curval
        self.context['curname'] = curname
        if not (group_id and month and year):
            return


        self.context['headers'] = map(lambda x: x[0], self.columns)

        rows = []

        group = Group.get(group_id)

        for user_id in group.users:
            user = CommCareUser.get(user_id)
            row = []
            lg = LendingGroupAggregate(user.full_name, [user._id], month, year, curval, curname)
            for v in self.columns:
                if v[1]:
                    row.append(getattr(lg, v[1]))
                else:
                    row.append('-')
            rows.append(row)

        self.context['rows'] = rows

class PerformanceReport(HQReport):
    name = "Project Performance"
    slug = "project_performance"
    template_name = "dca/project-performance.html"
    exportable = True
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'corehq.apps.reports.fields.GroupField', 'dca.reports.CurrencySelectionField']

    # Aggregate, %, Avg
    _rows = [
        ('Number of groups', 'num_groups', '', ''),
        ('Total number of current members', 'sum__active_members_at_time_of_visit', '', 'avg__active_members_at_time_of_visit'),
        ('Total men', 'sum__active_men_at_time_of_visit', '', 'avg__active_men_at_time_of_visit'),
        ('Total women', 'sum__active_women_at_time_of_visit', '', 'avg__active_women_at_time_of_visit'),
        ('Total number of supervised groups', 'num_groups', '', ''),
        ('Change in number of members this cycle', 'change_in_members','pct_change_in_members','avg_change_in_members'),
        ('Dropout rate', '', 'dropout_rate',''),
        ('Attendance rate', '','attendance_rate',''),
        ('Average age of group (weeks)', '','','avg_age_of_group'),
        ('Total assets', 'assets', '', 'avg_assets'),
        ('Loan fund cash on hand', 'loan_fund_cash_in_box_at_bank', '', 'avg_loan_fund_cash_in_box_at_bank'),
        ('Value of loans outstanding', 'value_of_loans_outstanding', '', 'avg_value_of_loans_outstanding'),
        ('Property', 'property_now', '', 'avg_property_now'),
        ('Total liabilities and equity', 'liabilities_and_equity', '', 'avg_liabilities_and_equity'),
        ('Total value of savings this cycle', 'value_of_savings', '', 'avg_value_of_savings'),
        ('Number of loans outstanding', 'loans_outstanding', '', 'avg_loans_outstanding')

    ]

    def calc(self):
        group_id = self.request.GET.get("group", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        curval = float(self.request.GET.get("curval", 1.0))
        curname = self.request.GET.get("curname", "MK")
        if not (group_id and month and year):
            return

        headers = ["Statistic", "Aggregate (All Groups)", "%", "Average (Per Group)"]

        group = Group.get(group_id)

        lg = LendingGroupAggregate(group.name, group.users, month, year, curval, curname)

        self.context['headers'] = headers
        self.context['rows'] = []
        for r in self._rows:
            row = [r[0]]
            def _ga(x):
                if x:
                    return getattr(lg, x)
                return ''
            row.extend(map(_ga, r[1:]))
            self.context['rows'].append(row)



        