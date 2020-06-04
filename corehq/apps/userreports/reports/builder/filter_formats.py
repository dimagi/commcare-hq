from corehq.apps.userreports.reports.builder import const


def get_pre_filter_format(pre_filter_dict):
    """
    See the `to_report_filter` function of DataSourceProperty in forms.py for this logic.
    This is basically the opposite.
    """
    return 'Value' if pre_filter_dict['pre_value'] else 'Date'
