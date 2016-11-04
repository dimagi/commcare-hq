from .couch import get_document_or_404
from .view_utils import reverse


def remove_dups(list_of_dicts, unique_key):
    keys = set([])
    ret = []
    for d in list_of_dicts:
        if d.get(unique_key) not in keys:
            keys.add(d.get(unique_key))
            ret.append(d)
    return ret
