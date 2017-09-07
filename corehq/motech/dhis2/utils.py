from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
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


def get_previous_month(send_date):
    enddate = date(year=send_date.year, month=send_date.month, day=1) - timedelta(days=1)
    startdate = date(year=enddate.year, month=enddate.month, day=1)
    return DateSpan(startdate, enddate)


def get_previous_quarter(send_date):
    current_quarter_start = (((send_date.month - 1) // 3) * 3) + 1
    startdate = date(year=send_date.year, month=current_quarter_start, day=1) - relativedelta(months=3)
    enddate = date(year=send_date.year, month=current_quarter_start, day=1) + relativedelta(months=4) - \
        timedelta(days=1) - relativedelta(months=3)
    return DateSpan(startdate, enddate)


def get_date_params(slug, date_span):
    """
    Mimics date filter request parameters
    """
    startdate = date_span.startdate.strftime('%Y-%m-%d')
    enddate = date_span.enddate.strftime('%Y-%m-%d')
    return {
        slug: "{}+to+{}".format(startdate, enddate),
        slug + '-start': startdate,
        slug + '-end': enddate,
    }


def get_ucr_data(report_config, date_filter, date_span):
    from corehq.apps.userreports.reports.view import get_filter_values

    data_source = ConfigurableReportDataSource.from_spec(report_config, include_prefilters=True)

    filter_params = get_date_params(date_filter['slug'], date_span) if date_filter else {}
    filter_values = get_filter_values(report_config.ui_filters, filter_params)
    data_source.set_filter_values(filter_values)
    return data_source.get_data()


def fetch_id_display_name_dict(api, list_endpoint):
    item_dict = {
        # '<id>': {
        #     'id': '<id>',
        #     'name': '<displayName>',
        # },
        # # ...
    }
    resp = api.get(list_endpoint, params={'paging': 'false'})
    resp_json = resp.json()
    for item in resp_json[list_endpoint]:
        item_id = item['id']
        item_dict[item_id] = {
            'id': item_id,
            'name': item['displayName'],
        }
    return item_dict


def fetch_data_sets(api, data_elements, category_option_combos):
    data_sets = {
        # '<id>': {
        #     'id': '<id>',
        #     'name': '<displayName>',
        #     'data_elements': {
        #         '<id>': {
        #             'id': '<id>',
        #             'name': '<displayName>',
        #         },
        #         # ...
        #     },
        #     'category_option_combos': {
        #         '<id>': {
        #             'id': '<id>',
        #             'name': '<displayName>',
        #         },
        #         # ...
        #     }
        # },
        # # ...
    }
    resp = api.get('dataSets', params={'paging': 'false'})
    data_sets_json = resp.json()  # {"dataSets":[{"id":"lyLU2wR22tC","displayName":"ART monthly summary"},...]}
    for data_set in data_sets_json['dataSets']:
        data_set_id = data_set['id']
        # Get details for each data set to find its data elements
        resp = api.get('dataSets/' + data_set_id)
        data_set_json = resp.json()
        data_sets[data_set_id] = {
            'id': data_set_id,
            'name': data_set['displayName'],
            'data_elements': {},
            'category_option_combos': {},
        }
        for data_set_element in data_set_json['dataSetElements']:
            data_element_id = data_set_element['dataElement']['id']
            try:
                data_sets[data_set_id]['data_elements'][data_element_id] = data_elements[data_element_id]
            except KeyError:
                # TODO: This is a good place to log the fact that a data element of the data set was not found
                pass
        resp = api.get('categoryCombos/' + data_set_json['categoryCombo']['id'])
        category_combo_json = resp.json()
        if 'categoryOptionCombos' in category_combo_json:
            for category_option_combo in category_combo_json['categoryOptionCombos']:
                coc_id = category_option_combo['id']
                try:
                    data_sets[data_set_id]['category_option_combos'][coc_id] = category_option_combos[coc_id]
                except KeyError:
                    # TODO: Logging
                    pass
    return data_sets


def fetch_dhis2_id_display_names(api):
    """
    Fetches IDs and display names from DHIS2 for dropdowns in HQ
    """
    data_elements = fetch_id_display_name_dict(api, 'dataElements')
    category_option_combos = fetch_id_display_name_dict(api, 'categoryOptionCombos')
    data_sets = fetch_data_sets(api, data_elements, category_option_combos)
    return data_sets
