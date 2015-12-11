def values_list(hits, *fields, **kwargs):
    """modeled after django's QuerySet.values_list"""
    flat = kwargs.pop('flat', False)
    if kwargs:
        raise TypeError('Unexpected keyword arguments to values_list: %s'
                        % (list(kwargs),))
    if flat and len(fields) > 1:
        raise TypeError("'flat' is not valid when values_list is called with more than one field.")
    if not fields:
        raise TypeError('must be called with at least one field')
    if flat:
        field, = fields
        return [hit[field] for hit in hits]
    else:
        return [tuple(hit[field] for field in fields) for hit in hits]
