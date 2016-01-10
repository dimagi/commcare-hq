from corehq.apps.domain.models import Domain
from corehq.util.couch import get_db_by_doc_type
from corehq.util.test_utils import unit_testing_only


def get_doc_count_in_domain_by_class(domain, doc_class):
    doc_type = doc_class.__name__
    row = doc_class.get_db().view(
        "by_domain_doc_type_date/view",
        startkey=[domain, doc_type],
        endkey=[domain, doc_type, {}],
        reduce=True,
    ).one()
    return row["value"] if row else 0


def get_doc_ids_in_domain_by_class(domain, doc_class):
    db = doc_class.get_db()
    doc_type = doc_class.__name__
    return get_doc_ids_in_domain_by_type(domain, doc_type, db)


def get_doc_ids_in_domain_by_type(domain, doc_type, database=None):
    """
    Given a domain and doc type, get all docs matching that domain and type
    """
    if not database:
        database = get_db_by_doc_type(doc_type)
    return [row['id'] for row in database.view('by_domain_doc_type_date/view',
        startkey=[domain, doc_type],
        endkey=[domain, doc_type, {}],
        reduce=False,
        include_docs=False,
    )]


def get_docs_in_domain_by_class(domain, doc_class):
    """
    Given a domain and doc class, get all docs matching that domain and type

    in order to prevent this from being used on a doc_class with many docs per domain
    doc_class must be white-listed.
    """
    whitelist = [
        'CallCenterIndicatorConfig',
        'CommCareCaseGroup',
        'CommtrackConfig',
        'HQGroupExportConfiguration',
        'Group',
        'Invitation',
        'PerformanceConfiguration',
        'ReportConfiguration',
    ]
    doc_type = doc_class.__name__
    assert doc_type in whitelist
    return doc_class.view(
        'by_domain_doc_type_date/view',
        startkey=[domain, doc_type],
        endkey=[domain, doc_type, {}],
        reduce=False,
        include_docs=True,
    ).all()


def get_domain_ids_by_names(names):
    return [result['id'] for result in Domain.view(
        "domain/domains",
        keys=names,
        reduce=False,
        include_docs=False
    )]
