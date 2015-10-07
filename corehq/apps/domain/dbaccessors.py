def get_doc_ids_in_domain_by_type(domain, doc_class):
    db = doc_class.get_db()
    doc_type = doc_class.__name__
    key = [domain, doc_type]
    results = db.view('domain/docs', startkey=key, endkey=key + [{}], reduce=False)
    return [result['id'] for result in results]
