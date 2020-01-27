def map_reduce(emitfunc=lambda rec: [(None,)], reducefunc=lambda v: v, data=None, include_docs=False):
    """perform a "map-reduce" on the data

    emitfunc(rec): return an iterable of key-value pairings as (key, value). alternatively, may
        simply emit (key,) (useful for include_docs=True or reducefunc=len)
    reducefunc(values): applied to each list of values with the same key; defaults to just
        returning the list
    data: list of records to operate on. defaults to data loaded from load()
    include_docs: if True, each emitted value v will be implicitly converted to (v, doc) (if
        only key is emitted, v == doc)
    """

    mapped = {}
    for rec in data:
        for emission in emitfunc(rec):
            try:
                k, v = emission
                if include_docs:
                    v = (v, rec)
            except ValueError:
                k, v = emission[0], rec if include_docs else None
            if k not in mapped:
                mapped[k] = []
            mapped[k].append(v)
    return dict((k, reducefunc(v)) for k, v in mapped.items())
