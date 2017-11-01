from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.userreports.models import get_report_config
from corehq.apps.userreports.columns import get_expanded_column_config


def get_expanded_columns(column_configs, data_source_config):
    return {
        column_config.column_id: [
            sql_col.slug for sql_col in get_expanded_column_config(
                data_source_config, column_config, 'en'
            ).columns
        ]
        for column_config in column_configs
        if column_config.type == 'expanded'
    }


def has_location_filter(view_fn, *args, **kwargs):
    """check that the report has at least one location based filter or
    location choice provider filter
    """
    report, _ = get_report_config(config_id=kwargs.get('subreport_slug'), domain=kwargs.get('domain'))
    return any(
        getattr(getattr(filter_, 'choice_provider', None), 'location_safe', False) or
        getattr(filter_, 'location_filter', False)
        for filter_ in report.ui_filters
    )
