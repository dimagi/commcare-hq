from collections import namedtuple
from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_LEDGER
from corehq.apps.app_manager.util import create_temp_sort_column


def get_default_sort_elements(detail):
    from corehq.apps.app_manager.models import SortElement

    if not detail.columns:
        return []

    def get_sort_params(column):
        if column.field_type == FIELD_TYPE_LEDGER:
            return dict(type='int', direction='descending')
        else:
            return dict(type='string', direction='ascending')

    col_0 = detail.get_column(0)
    sort_elements = [SortElement(
        field=col_0.field,
        **get_sort_params(col_0)
    )]

    for column in detail.columns[1:]:
        if column.field_type == FIELD_TYPE_LEDGER:
            sort_elements.append(SortElement(
                field=column.field,
                **get_sort_params(column)
            ))

    return sort_elements


def get_detail_column_infos(detail, include_sort):
    """
    This is not intented to be a widely used format
    just a packaging of column info into a form most convenient for rendering
    """
    DetailColumnInfo = namedtuple('DetailColumnInfo',
                                  'column sort_element order')
    if not include_sort:
        return [DetailColumnInfo(column, None, None) for column in detail.get_columns()]

    if detail.sort_elements:
        sort_elements = detail.sort_elements
    else:
        sort_elements = get_default_sort_elements(detail)

    # order is 1-indexed
    sort_elements = {s.field: (s, i + 1)
                     for i, s in enumerate(sort_elements)}
    columns = []
    for column in detail.get_columns():
        sort_element, order = sort_elements.pop(column.field, (None, None))
        columns.append(DetailColumnInfo(column, sort_element, order))

    # sort elements is now populated with only what's not in any column
    # add invisible columns for these
    sort_only = sorted(sort_elements.items(),
                       key=lambda (field, (sort_element, order)): order)

    for field, (sort_element, order) in sort_only:
        column = create_temp_sort_column(field, len(columns))
        columns.append(DetailColumnInfo(column, sort_element, order))
    return columns
