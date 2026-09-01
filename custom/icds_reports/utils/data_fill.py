from custom.icds_reports.tasks import _agg_governance_dashboard
from datetime import date
from dateutil.relativedelta import relativedelta


current_month = date(2019, 11, 1)


while current_month >= date(2019, 4, 1):
    _agg_governance_dashboard(current_month)
    # subtracting two months because function internally aggregates
    # for two months hence going two months back not one month back
    current_month -= relativedelta(months=2)

