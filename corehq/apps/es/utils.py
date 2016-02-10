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


def flatten_field_dict(results, fields_property='fields'):
    """
    In ElasticSearch 1.3, the return format was changed such that field
    values are always returned as lists, where as previously they would
    be returned as scalars if the field had a single value, and returned
    as lists if the field had multiple values.
    This method restores the behavior of 0.90 .

    https://www.elastic.co/guide/en/elasticsearch/reference/1.3/_return_values.html
    """
    field_dict = results.get(fields_property, {})
    for key, val in field_dict.iteritems():
        new_val = val
        if type(val) == list and len(val) == 1:
            new_val = val[0]
        field_dict[key] = new_val
    return field_dict
