from copy import deepcopy


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


def chunk_query(query, term, chunk_size=1000):
    '''
    This takes a ESQuery and a term and then chunks the query into identical queries
    except having chunked the term. For example, if you have a query that has 100,000
    queries and the chunk_size is 1000, it will return 100 queries.

    :param query: An ESQuery
    :param term: A term that you wish to be chunked, such as 'form.meta.userID'
    :param chunk_size: The chunk size

    :return: If it cannot find anything to chunk or the chunked term is not an array,
        it will just return the same query wrapped in an array. Otherwise, it will return
        an array of ESQuerys with the chunked term.

    '''
    query = deepcopy(query)

    path_to_term = _chunk_query([], None, query.es_query, term)
    chunked_queries = []

    # No path to term could be found, return just the query
    if path_to_term is None:
        return [query]

    term_list = _dict_lookup(path_to_term, query.es_query)

    # Cannot chunk term that is not a list
    if not isinstance(term_list, list):
        return [query]

    for index in xrange(0, len(term_list), chunk_size):
        terms = term_list[index:index + chunk_size]
        chunked_query = deepcopy(query)

        # Set query to the chunk
        _dict_lookup(path_to_term[:-1], chunked_query.es_query)[term] = terms

        chunked_queries.append(chunked_query)

    return chunked_queries


def _dict_lookup(path, dict_):
    partial = dict_
    for part in path:
        try:
            partial = partial[part]
        except IndexError:
            return None
    return partial


def _chunk_query(path_to_term, key, es_query, term):
    if key is not None:
        path_to_term.append(key)
    if key == term:
        return path_to_term

    if isinstance(es_query, dict):
        for key, partial_query in es_query.iteritems():
            result = _chunk_query(list(path_to_term), key, partial_query, term)
            if result:
                return result
    elif isinstance(es_query, list):
        for index, partial_query in enumerate(es_query):
            result = _chunk_query(list(path_to_term), index, partial_query, term)
            if result:
                return result

    return None
