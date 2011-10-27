def intersect_filters(*args):
    filters = [fn for fn in args if fn]
    if filters:
        def filter(doc):
            for fn in filters:
                if not fn(doc):
                    return False
            return True
    else:
        filter = None
    return filter