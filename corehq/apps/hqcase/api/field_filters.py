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
    raise NotImplementedError
