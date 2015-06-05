from corehq.apps.tzmigration import set_migration_started, \
    set_migration_complete


def run_timezone_migration_for_domain(domain):
    set_migration_started(domain)
    _run_timezone_migration_for_domain(domain)
    set_migration_complete(domain)


def _json_diff(obj1, obj2, path):
    if isinstance(obj1, str):
        obj1 = unicode(obj1)
    if isinstance(obj2, str):
        obj2 = unicode(obj2)

    if obj1 == obj2:
        return
    elif Ellipsis in (obj1, obj2):
        yield 'missing', path, obj1, obj2
    elif type(obj1) != type(obj2):
        yield 'type',  path, obj1, obj2
    elif isinstance(obj1, dict):
        keys = set(obj1.keys()) | set(obj2.keys())

        def value_or_ellipsis(obj, key):
            return obj.get(key, Ellipsis)

        for key in keys:
            for result in _json_diff(value_or_ellipsis(obj1, key),
                                     value_or_ellipsis(obj2, key),
                                     path=path + (key,)):
                yield result
    elif isinstance(obj1, list):

        def value_or_ellipsis(obj, i):
            try:
                return obj[i]
            except IndexError:
                return Ellipsis

        for i in range(max(len(obj1), len(obj2))):
            for result in _json_diff(value_or_ellipsis(obj1, i),
                                     value_or_ellipsis(obj2, i),
                                     path=path + (i,)):
                yield result
    else:
        yield 'diff', path, obj1, obj2


def json_diff(obj1, obj2):
    items = []
    for type_, path, val1, val2 in _json_diff(obj1, obj2, path=()):
        assert type_ in ('missing', 'type', 'diff')
        items.append((type_, path, val1, val2))
    return items


def _run_timezone_migration_for_domain(domain):
    pass
