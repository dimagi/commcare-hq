
def _clean_json(doc):
    if not isinstance(doc, dict):
        return doc
    doc.pop('domain', None)
    doc.pop('doc_type', None)
    doc.pop('_id', None)
    doc.pop('_rev', None)
    for key, val in doc.items():
        if isinstance(val, dict):
            _clean_json(val)
        if isinstance(val, list):
            map(_clean_json, val)
    return doc
