from corehq.apps.hqcase.api.core import UserError

FIELDS_PARAM = 'fields'
EXCLUDE_PARAM = 'exclude'


def extract_fields_params(params):
    """Read 'fields'/'exclude' params from QueryDict, return filter function.

    Reads but does not pop params from the QueryDict. The params remain
    in the QueryDict so they are preserved in pagination cursors.

    Returns a callable (dict -> dict) that applies field filtering.
    Returns the identity function if neither fields nor exclude was specified.
    """
    has_fields, fields_spec = _collect_field_spec(params, FIELDS_PARAM)
    has_exclude, exclude_spec = _collect_field_spec(params, EXCLUDE_PARAM)

    if has_fields and has_exclude:
        raise UserError("You cannot specify both 'fields' and 'exclude'")

    if has_fields:
        tree = _build_field_tree(fields_spec)
        return lambda data: _limit_fields(data, tree)
    if has_exclude:
        tree = _build_field_tree(exclude_spec)
        return lambda data: _exclude_fields(data, tree)
    return _identity


def _identity(data):
    return data


def _collect_field_spec(params, prefix):
    """Collect field paths from a QueryDict for the given prefix.

    Reads 'prefix' and all 'prefix.*' keys. Values are comma-separated.
    Returns (key_present, fields) where key_present is True if any
    matching keys exist in the QueryDict (even if values are empty).
    """
    fields = []
    key_present = False
    for key in list(params.keys()):
        if key == prefix:
            key_present = True
            for value in params.getlist(key):
                fields.extend(part.strip() for part in value.split(",") if part.strip())
        elif key.startswith(prefix + "."):
            key_present = True
            nesting = key[len(prefix) + 1:]  # e.g. "properties" from "fields.properties"
            for value in params.getlist(key):
                for part in value.split(","):
                    part = part.strip()
                    if part:
                        fields.append(f"{nesting}.{part}")
    return key_present, fields


def _build_field_tree(fields):
    """Build a nested dict (field tree) from a list of dot-separated field paths.

    A leaf ({}) means "include/exclude this entire value."
    A branch (non-empty dict) means "descend and apply sub-tree."
    """
    tree = {}
    for field in fields:
        parts = field.split(".")
        node = tree
        for part in parts[:-1]:
            if part in node and node[part] == {}:
                break
            node = node.setdefault(part, {})
        else:
            last = parts[-1]
            if last in node and isinstance(node[last], dict) and node[last]:
                node[last] = {}
            else:
                node.setdefault(last, {})
    return tree


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
