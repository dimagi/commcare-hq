
def sorted_mapping(mapping):
    """Return a recursively sorted Elastic mapping."""
    if isinstance(mapping, dict):
        mapping_ = {}
        for key, value in sorted(mapping.items(), key=mapping_sort_key):
            mapping_[key] = sorted_mapping(value)
        return mapping_
    if isinstance(mapping, (tuple, list)):
        return [sorted_mapping(item) for item in mapping]
    return mapping


def mapping_sort_key(item):
    key, value = item
    return 1 if key == "properties" else 0, key, value
