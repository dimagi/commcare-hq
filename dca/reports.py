from corehq.apps.reports.custom import HQReport, ReportField
from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group

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

        tmp = get_db().view('dca/dca_collection_forms_by_case', startkey=[self.case['_id'], month, year],
            endkey=[self.case['_id'], month, year, {}], include_docs=True, limit=1).all()
        if len(tmp):
            self.coll = tmp[0]

    def __getattr__(self, item):
        """
        Check the collection (will have data from the relevant month) and fall back to the case if the info isn't
        there.
        """
        try:
            return self.coll['doc']['form'][item]
        except TypeError, KeyError:
            try:
                return self.case[item]
            except KeyError:
                raise AttributeError("Couldn't find %s in either the collection or the case.")


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

    def _all(self, l):
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

    # Columns
    @property
    def num_groups(self):
        return len(self.groups)

    @property
    def num_members(self):
        return self.sum_all_groups(lambda x: x.active_members_at_time_of_visit)

    @property
    def members_at_start_of_cycle(self):
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
    def _value_of_loans_outstanding(self):
        return self.sum_all_groups(lambda x: x.value_of_loans_outstanding)

    @property
    def value_of_loans_outstanding(self):
        return self.currency(self.value_of_loans_outstanding)

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
    def _value_of_savings(self):
        return self.sum_all_groups(lambda x: x.value_of_savings_this_cycle)

    @property
    def value_of_savings(self):
        return self.currency(self._value_of_savings)

    @property
    def _loan_fund_cash_in_box_at_bank(self):
        return self.sum_all_groups(lambda x: x.loan_fund_cash_in_box_at_bank)

    @property
    def loan_fund_cash_in_box_at_bank(self):
        return self.currency(self._loan_fund_cash_in_box_at_bank)

    @property
    def loan_fund_utilization(self):
        return self.pct(self._value_of_loans_outstanding, self._value_of_loans_outstanding+self._loan_fund_cash_in_box_at_bank)

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
                    row.append(lg.__getattribute__(v[1]))
                else:
                    row.append('-')
            rows.append(row)

        self.context['rows'] = rows