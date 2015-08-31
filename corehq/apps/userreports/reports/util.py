from django.utils.translation import ugettext


def get_total_row(data, aggregation_columns, column_configs):
    total_row = [0] * len(column_configs)
    for i, column_config in enumerate(column_configs):
        if column_config.calculate_total:
            total_row[i] = reduce(
                lambda x, y: (
                    x + y
                    if isinstance(x, (int, long, float)) and isinstance(y, (int, long, float))
                    else ''
                ),
                map(lambda row: row[column_config.column_id], data),
                0
            )
        else:
            total_row[i] = ''
    if total_row[0] == '' and aggregation_columns:
        total_row[0] = ugettext('Total')
    return total_row
