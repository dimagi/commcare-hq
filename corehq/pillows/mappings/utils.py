from corehq.apps.es.exceptions import ESError
from corehq.elastic import get_es_new


def fetch_elastic_mapping(index, type_, elastic=None):
    """Fetches the mapping for a type of document from an index.

    :param index: Elastic index name or alias (string).
    :param type_: Elastic type in `index` (string).

    WARNING: this will not necessarily return the mapping the index was created
    or updated with. The `/<index>/_mapping[/<type_>]` request only returns
    fields present in documents which have been _indexed so far_. If you create
    a new index and immediately fetch its mapping, the mapping will be empty. If
    you add documents and then fetch the mapping for those document's type, the
    mapping will only contain fields which were present in the indexed
    documents, and still lack the other fields that were included when the index
    was created.  The docs suggest that the `include_defaults` parameter will
    'cause the response to include default values, which are normally
    suppressed', but not only does that not help with this problem, it doesn't
    even do what it claims to do (defaults are still suppressed, for example:
    "index": "analyzed", "type": "object", etc).
    """
    if elastic is None:
        elastic = get_es_new()
    response = elastic.get(index, "_mapping", type_)  # params={"include_defaults": True})
    # The only key in the response is the full index name, but the `index` arg
    # passed to this function might be an alias, so we just pop and ignore its
    # value.
    mappings = response.pop(next(iter(response.keys())))["mappings"]
    mapping_for_type = mappings.pop(type_)
    # enforce that the response only had one item with mappings for one type
    if response:
        raise ESError(f"unexpected response data: {response}")
    if mappings:
        raise ESError(f"unexpected mappings data: {mappings}")
    return sorted_mapping(mapping_for_type)


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
