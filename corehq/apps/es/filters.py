"""
Available Filters
-----------------

The following filters are available on any ESQuery instance - you can chain
any of these on your query.

Contributing:
Additions to this file should be added to the ``builtin_filters`` method on
either ESQuery or HQESQuery, as appropriate (is it an HQ thing?).
"""


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


def NOT(filter):
    """
    Exclude docs matching the filter passed in
    """
    return {"not": filter}


def range_filter(field, gt=None, gte=None, lt=None, lte=None):
    """
    You must specify either gt (greater than) or gte (greater than or
    equal to) and either lt or lte.
    """
    return {"range": {field: {
        k: v for k, v in {'gt': gt, 'gte': gte, 'lt': lt, 'lte': lte}.items()
        if v is not None
    }}}


def date_range(field, gt=None, gte=None, lt=None, lte=None):
    def format_date(date):
        # TODO This probably needs more sophistication...
        return date.isoformat()
    params = [d if d is None else format_date(d) for d in [gt, gte, lt, lte]]
    return range_filter(field, *params)


def domain(domain):
    return term('domain.exact', domain)


def doc_type(doc_type):
    return term('doc_type', doc_type)


def doc_id(doc_id):
    return term("_id", doc_id)


def missing(field, exist=True, null=True):
    return {
        "missing": {
            "field": field,
            "existence": exist,
            "null_value": null
        }
    }


def exists(field):
    """
    Only return docs which have 'field'
    """
    return {"exists": {"field": field}}


def empty(field):
    return OR({'missing': {'field': field, "existence": True, "null_value": True}},
              term(field, ''))
