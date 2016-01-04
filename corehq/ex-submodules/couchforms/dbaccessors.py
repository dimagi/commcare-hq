from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.util.test_utils import unit_testing_only
from couchforms.const import DEVICE_LOG_XMLNS
from couchforms.models import XFormInstance, doc_types


def get_form_ids_by_type(domain, type_, start=None, end=None):
    assert type_ in doc_types()
    startkey = [domain, type_]
    if end:
        endkey = startkey + end.isoformat()
    else:
        endkey = startkey + [{}]

    if start:
        startkey.append(start.isoformat())

    return [row['id'] for row in XFormInstance.get_db().view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False,
    )]


def get_forms_by_type(domain, type_, recent_first=False,
                      limit=None):
    assert type_ in doc_types()
    # no production code should be pulling all forms in one go!
    assert limit is not None
    startkey = [domain, type_]
    endkey = startkey + [{}]
    if recent_first:
        startkey, endkey = endkey, startkey
    return XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        descending=recent_first,
        include_docs=True,
        limit=limit,
        classes=doc_types(),
    ).all()


@unit_testing_only
def get_forms_of_all_types(domain):
    startkey = [domain]
    endkey = startkey + [{}]
    return XFormInstance.view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False,
        include_docs=True,
        classes=doc_types(),
    ).all()


@unit_testing_only
def get_commtrack_forms(domain):
    key = ['submission xmlns', domain, COMMTRACK_REPORT_XMLNS]
    return XFormInstance.view(
        'all_forms/view',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
        include_docs=True
    )
