from corehq.apps.domain.models import Domain
from corehq.util.couch import get_db_by_doc_type
from corehq.util.couch_helpers import paginate_view
from dimagi.utils.parsing import json_format_datetime


def get_doc_count_in_domain_by_class(domain, doc_class, start_date=None, end_date=None):
    doc_type = doc_class.__name__
    return get_doc_count_in_domain_by_type(domain, doc_type, doc_class.get_db(),
                                           start_date=start_date, end_date=end_date)


def get_doc_count_in_domain_by_type(domain, doc_type, db, start_date=None, end_date=None):
    start_key = [domain, doc_type]
    end_key = [domain, doc_type]
    if start_date is not None:
        start_key.append(json_format_datetime(start_date))
    if end_date is not None:
        end_key.append(json_format_datetime(end_date))
    end_key.append({})

    row = db.view(
        "by_domain_doc_type_date/view",
        startkey=start_key,
        endkey=end_key,
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


def iterate_doc_ids_in_domain_by_type(domain, doc_type, chunk_size=10000,
                                      database=None, startkey=None, startkey_docid=None):

    if not database:
        database = get_db_by_doc_type(doc_type)

    view_kwargs = {
        'reduce': False,
        'startkey': startkey if startkey else [domain, doc_type],
        'endkey': [domain, doc_type, {}],
        'include_docs': False
    }
    if startkey_docid:
        view_kwargs.update({
            'startkey_docid': startkey_docid
        })
    for doc in paginate_view(
            database,
            'by_domain_doc_type_date/view',
            chunk_size,
            **view_kwargs):
        yield doc['id']


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
        'UserRole',
        'Invitation',
        'PerformanceConfiguration',
        'ReportConfiguration',
        'CaseReminderHandler',
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


def count_downloads_for_all_snapshots(domain_id):
    """
    domain_id should represent an actual (non-snapshot) domain for this to make sense
    but that is not checked. It'll just be 0 otherwise.
    """

    try:
        return Domain.get_db().view(
            'domain/snapshots',
            startkey=[domain_id],
            endkey=[domain_id, {}],
            reduce=True,
            include_docs=False,
        ).one()["value"]
    except TypeError:
        return 0
