from corehq.apps.userreports.models import get_report_config
from corehq.apps.userreports.sql import get_expanded_column_config


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
    """check that the report has at least one location choice provider filter
    """
    report, _ = get_report_config(config_id=kwargs.get('subreport_slug'), domain=kwargs.get('domain'))
    return any(
        filter_.choice_provider.location_safe
        if hasattr(filter_, 'choice_provider') else False
        for filter_ in report.ui_filters
    )
