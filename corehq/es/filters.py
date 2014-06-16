def term(field, value):
    """
    Filter docs by a field

    'value' can be a singleton or a list.
    """
    if isinstance(value, list):
        return {"terms": {field: value}}
    else:
        return {"term": {field: value}}


def OR(**filters):
    return {"or": filters}


def range_filter(field, gt=None, gte=None, lt=None, lte=None):
    """
    You must specify either gt (greater than) or gte (greater than or
    equal to) and either lt or lte.
    """
    assert (gt and (lt or lte)) or (gte and (lt or lte))
    return {"range": {field: {
        'gt' if gt else 'gte': gt or gte,
        'lt' if lt else 'lte': lt or lte
    }}}


def date_range(field, gt=None, gte=None, lt=None, lte=None):
    def format_date(date):
        # TODO I assume we need to coerce to a string date here?
        return date
    params = [format_date(d) for d in [gt, gte, lt, lte] if d is not None]
    return range_filter(field, **params)
