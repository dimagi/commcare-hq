from dimagi.utils.couch.database import get_db


def get_doc_ids_in_domain_by_type(domain, doc_class):
    db = doc_class.get_db()
    doc_type = doc_class.__name__
    key = [domain, doc_type]
    results = db.view('domain/docs', startkey=key, endkey=key + [{}], reduce=False)
    return [result['id'] for result in results]


def get_doc_ids(domain, doc_type, database=None):
    """
    Given a domain and doc type, get all docs matching that domain and type
    """
    if not database:
        database = get_db()
    return [row['id'] for row in database.view('domain/docs',
        startkey=[domain, doc_type],
        endkey=[domain, doc_type, {}],
        reduce=False,
        include_docs=False,
    )]
