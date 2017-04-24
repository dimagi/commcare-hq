from datetime import date, timedelta
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.util.couch import get_document_or_not_found
from dimagi.utils.dates import DateSpan


def get_report_config(domain_name, ucr_id):
    report_config = get_document_or_not_found(ReportConfiguration, domain_name, ucr_id)
    return report_config


def get_date_filter(report_config):
    """
    Returns the first date filter, or None.

    Assumes the first date filter is the one to use.

    .. NOTE: The user might not want to filter by date for DHIS2
             integration. They can use a "period" column to return
             rows for multiple periods, or set a period for the report
             if it is always for the same period.
    """
    date_filter = next((f for f in report_config.filters if f['type'] == 'date'), None)
    return date_filter


def get_last_month():
    today = date.today()
    enddate = date(year=today.year, month=today.month, day=1) - timedelta(days=1)
    startdate = date(year=enddate.year, month=enddate.month, day=1)
    return DateSpan(startdate, enddate)


def get_last_month_params(slug):
    """
    Mimics date filter request parameters
    """
    last_month = get_last_month()
    startdate = last_month.startdate.strftime('%Y-%m-%d')
    enddate = last_month.enddate.strftime('%Y-%m-%d')
    return {
        slug: "{}+to+{}".format(startdate, enddate),
        slug + '-start': startdate,
        slug + '-end': enddate,
    }


def get_ucr_data(report_config, date_filter):
    from corehq.apps.userreports.reports.view import get_filter_values

    data_source = ReportFactory.from_spec(report_config, include_prefilters=True)
    filter_params = get_last_month_params(date_filter['slug']) if date_filter else {}
    filter_values = get_filter_values(report_config.ui_filters, filter_params)
    data_source.set_filter_values(filter_values)
    return data_source.get_data()
