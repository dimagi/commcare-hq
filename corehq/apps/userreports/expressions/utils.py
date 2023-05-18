SUM = 'sum'
COUNT = 'count'
MIN = 'min'
MAX = 'max'
FIRST_ITEM = 'first_item'
LAST_ITEM = 'last_item'
JOIN = 'join'
SUPPORTED_UCR_AGGREGATIONS = [SUM, COUNT, MIN, MAX, FIRST_ITEM, LAST_ITEM, JOIN]


def aggregate_items(items, fn_name):

    aggregation_fn_map = {
        SUM: _sum,
        COUNT: _count,
        MIN: _min,
        MAX: _max,
        FIRST_ITEM: _first_item,
        LAST_ITEM: _last_item,
        JOIN: _join,
    }

    if not isinstance(items, list):
        return None

    assert fn_name in SUPPORTED_UCR_AGGREGATIONS
    aggregation_fn = aggregation_fn_map[fn_name]
    return aggregation_fn(items)


def _sum(items):
    return _type_safe_agggregate(sum, items)


def _min(items):
    if not items:
        return None
    return _type_safe_agggregate(min, items)


def _max(items):
    if not items:
        return None
    return _type_safe_agggregate(max, items)


def _type_safe_agggregate(aggregate_fn, items):
    try:
        return aggregate_fn(items)
    except TypeError:
        return None


def _count(items):
    return len(items)


def _first_item(items):
    try:
        return items[0]
    except (IndexError, TypeError):
        return None


def _last_item(items):
    try:
        return items[-1]
    except (IndexError, TypeError):
        return None


def _join(items):
    return ''.join(str(i) if i is not None else '' for i in items)
