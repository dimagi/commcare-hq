
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
            [_clean_json(inner_doc) for inner_doc in val]
    return doc


def convert_app_for_remote_linking(latest_master_build):
    _attachments = latest_master_build.get_attachments()
    source = latest_master_build.to_json()
    source['_LAZY_ATTACHMENTS'] = {
        name: {'content': content}
        for name, content in _attachments.items()
    }
    source.pop("external_blobs", None)
    return source
