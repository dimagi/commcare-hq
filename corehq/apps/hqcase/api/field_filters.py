from corehq.apps.hqcase.api.core import UserError


def get_fields_filter_fn(query_dict):
    fields = _get_tree(query_dict, 'fields')
    exclude = _get_tree(query_dict, 'exclude')
    if fields and exclude:
        raise UserError("You cannot specify both 'fields' and 'exclude'")

    if fields:
        return lambda data: _limit_fields(data, fields)
    if exclude:
        return lambda data: _exclude_fields(data, exclude)
    return lambda data: data


def _get_tree(query_dict, param_name):
    """Turn URL parameters into tree of properties to keep/exclude

    >>> qs = 'fields=case_id&fields=case_name&fields.properties=dob,edd'
    >>> _get_tree(QueryDict(qs), 'fields')
    {
        'case_id': {},
        'case_name': {},
        'properties': {'dob': {}, 'edd': {}},
    }
    """
    tree = {}
    for path in _extract_paths(query_dict, param_name):
        _add_to_tree(tree, path)
    return tree


def _extract_paths(query_dict, param_name):
    for p, vals in query_dict.lists():
        path = p.split('.')
        if path[0] == param_name:
            for val in vals:
                for v in val.split(','):
                    yield path[1:] + v.split('.')


def _add_to_tree(tree, path):
    if path:
        node = path[0]
        if node not in tree:
            tree[node] = {}
        _add_to_tree(tree[node], path[1:])


def _limit_fields(data, field_tree):
    """Return a copy of data containing only the fields in field_tree."""
    result = {}
    for key, subtree in field_tree.items():
        if key not in data:
            continue
        if not subtree:
            result[key] = data[key]
        elif isinstance(data[key], dict):
            result[key] = _limit_fields(data[key], subtree)
    return result


def _exclude_fields(data, field_tree):
    """Return a copy of data with the fields in field_tree removed."""
    result = {}
    for key, value in data.items():
        if key not in field_tree:
            result[key] = value
        elif field_tree[key]:
            if isinstance(value, dict):
                result[key] = _exclude_fields(value, field_tree[key])
            else:
                result[key] = value
    return result
