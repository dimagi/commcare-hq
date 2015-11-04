from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import get_db


def get_doc_ids_in_domain_by_class(domain, doc_class):
    db = doc_class.get_db()
    doc_type = doc_class.__name__
    return get_doc_ids_in_domain_by_type(domain, doc_type, db)


def get_doc_ids_in_domain_by_type(domain, doc_type, database=None):
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


def get_domain_ids_by_names(names):
    return [result['id'] for result in Domain.view(
        "domain/domains",
        keys=names,
        reduce=False,
        include_docs=False
    )]
