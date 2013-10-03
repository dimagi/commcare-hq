from custom.bihar.reports.indicators.reports import DEFAULT_EMPTY


def _format_date(d):
    try:
        return d.strftime('%d-%m-%Y')
    except AttributeError:
        return d


def husband_name(case):
    return getattr(case, "husband_name", DEFAULT_EMPTY)


def edd(case):
    return _format_date(getattr(case, "edd", DEFAULT_EMPTY))


def add(case):
    return _format_date(getattr(case, "add", DEFAULT_EMPTY))


def in_numerator(case, context):
    return case.get_id in context['numerator']


def in_denominator(case, context):
    return case.get_id in context['total']
