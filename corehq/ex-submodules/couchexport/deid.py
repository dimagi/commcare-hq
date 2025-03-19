from datetime import timedelta
from dimagi.utils.data.deid_generator import DeidGenerator
from memoized import memoized
from dimagi.utils.parsing import string_to_datetime
from functools import reduce


def deid_ID(val, doc):
    return DeidGenerator(val, 'id').random_hash()


@memoized
class JSONPath(object):

    def __init__(self, paths):
        self.paths = [path.split('/') for path in paths.split('|')]

    def search(self, doc):
        for path in self.paths:
            try:
                return reduce(lambda obj, attr: obj[attr], path, doc)
            except KeyError:
                pass


def deid_date(val, doc, key_path='form/case/@case_id|form/case/case_id|_id', key=None):
    if key is None:
        key = JSONPath(key_path).search(doc)
    if not key or not val:
        return None
    offset = DeidGenerator(key, 'date').random_number(-31, 32)
    orig_date = string_to_datetime(val)
    return (orig_date + timedelta(days=offset)).date()


def deid_remove(val, doc):
    return Ellipsis


def deid_map(doc, config):
    doc_copy = doc.copy()
    for key in config:
        parts = key.split('/')
        final_part = parts.pop()
        ctx = doc_copy
        for part in parts:
            ctx = ctx[part]
        if config[key]:
            ctx[final_part] = config[key](ctx[final_part], doc)
        if ctx[final_part] == Ellipsis:
            del ctx[final_part]
    return doc_copy
