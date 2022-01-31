
import testil

from corehq.elastic import get_es_new
from ..utils import sorted_mapping


def fetch_elastic_mapping(index, doc_type, elastic=None):
    """Fetches the mapping for a type of document from an index.

    :param index: Elastic index name or alias (string).
    :param doc_type: Elastic document type in `index` (string).

    WARNING: this will not necessarily return the mapping the index was created
    or updated with. The `/<index>/_mapping[/<doc_type>]` request only returns
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
    response = elastic.get(index, "_mapping", doc_type)  # params={"include_defaults": True})
    # The only key in the response is the full index name, but the `index` arg
    # passed to this function might be an alias, so we just pop and ignore its
    # value.
    mappings = response.pop(next(iter(response.keys())))["mappings"]
    # enforce that the response only had one item with mappings for one type
    testil.eq(response, {})
    mapping = mappings.pop(doc_type)
    testil.eq(mappings, {})
    return sorted_mapping(mapping)
