def match_all():
    return {"match_all": {}}


def term(field, value):
    """
    Filter docs by a field
    'value' can be a singleton or a list.
    """
    if isinstance(value, list):
        return {"terms": {field: value}}
    else:
        return {"term": {field: value}}


def OR(*filters):
    """
    Filter docs to match any of the filters passed in
    """
    return {"or": filters}


def AND(*filters):
    """
    Filter docs to match all of the filters passed in
    """
    return {"and": filters}


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
        # TODO This probably needs more sophistication...
        return date.isoformat()
    params = [format_date(d) for d in [gt, gte, lt, lte] if d is not None]
    return range_filter(field, **params)


def domain(domain):
    return term('domain.exact', domain)


def doc_type(doc_type):
    return term('doc_type', doc_type)
