from django.utils.translation import ugettext
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


def get_total_row(data, aggregation_columns, column_configs, column_id_to_expanded_column_ids):
    total_row = []
    for column_config in column_configs:
        column_ids = column_id_to_expanded_column_ids.get(column_config.column_id, [column_config.column_id])
        for column_id in column_ids:
            if column_config.calculate_total:
                total_row.append(reduce(
                    lambda x, y: (
                        x + y
                        if isinstance(x, (int, long, float)) and isinstance(y, (int, long, float))
                        else ''
                    ),
                    map(lambda row: row[column_id], data),
                    0
                ))
            else:
                total_row.append('')
    if total_row[0] == '' and aggregation_columns:
        total_row[0] = ugettext('Total')
    return total_row
