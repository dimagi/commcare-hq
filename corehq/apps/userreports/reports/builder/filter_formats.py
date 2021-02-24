from corehq.apps.userreports.reports.builder import const


def get_pre_filter_format(pre_filter_dict):
    """
    See the `to_report_filter` function of DataSourceProperty in forms.py for this logic.
    This is basically the opposite.
    """
    if pre_filter_dict['pre_operator'] == '' and pre_filter_dict['pre_value'] == '':
        return const.PRE_FILTER_VALUE_IS_EMPTY
    elif pre_filter_dict['pre_operator'] == '!=' and pre_filter_dict['pre_value'] == '':
        return const.PRE_FILTER_VALUE_EXISTS
    elif pre_filter_dict['pre_operator'] == 'distinct from':
        return const.PRE_FILTER_VALUE_NOT_EQUAL
    else:
        return const.FORMAT_VALUE if pre_filter_dict['pre_value'] else const.FORMAT_DATE
