from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime

from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.util.test_utils import unit_testing_only
from couchforms.models import XFormInstance, doc_types
from dimagi.utils.couch.database import iter_docs


def get_forms_by_id(form_ids):
    forms = iter_docs(XFormInstance.get_db(), form_ids)
    doctypes = doc_types()
    return [doctypes[form['doc_type']].wrap(form) for form in forms if form.get('doc_type') in doctypes]


def get_form_ids_by_type(domain, type_, start=None, end=None):
    assert type_ in doc_types()
    startkey = [domain, type_]
    if end:
        endkey = startkey + [end.isoformat()]
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
def get_commtrack_forms(domain):
    key = ['submission xmlns', domain, COMMTRACK_REPORT_XMLNS]
    return XFormInstance.view(
        'all_forms/view',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
        include_docs=True
    )


def get_deleted_form_ids_for_user(user_id):
    results = XFormInstance.get_db().view(
        'deleted_data/deleted_forms_by_user',
        startkey=[user_id],
        endkey=[user_id, {}],
        reduce=False,
        include_docs=False,
    )
    return [result['id'] for result in results]


def get_form_ids_for_user(domain, user_id):
    key = ['submission user', domain, user_id]
    results = XFormInstance.get_db().view(
        'all_forms/view',
        startkey=key,
        endkey=key + [{}],
        reduce=False,
        include_docs=False,
    )
    return [result['id'] for result in results]


def iter_form_ids_by_xmlns(domain, xmlns):
    if xmlns:
        key = ['submission xmlns', domain, xmlns]
    else:
        key = ['submission', domain]

    endkey = key + [datetime.utcnow().isoformat()]

    # pull the first 1000 documents sorted by submission time
    LIMIT = 1000
    results = XFormInstance.get_db().view(
        'all_forms/view',
        startkey=key,
        endkey=endkey,
        reduce=False,
        include_docs=False,
        limit=LIMIT,
        descending=False,
    ).all()

    while results:
        for result in results:
            yield result['id']

        # add the last document's received_on time to the startkey
        last_result = results[-1]
        startkey = key + [last_result['key'][-1]]

        # pull 1000 documents starting with the last document pulled in the previous iteration
        results = XFormInstance.get_db().view(
            'all_forms/view',
            startkey=startkey,
            endkey=endkey,
            reduce=False,
            include_docs=False,
            limit=LIMIT,
            descending=False,
        ).all()
        # remove the first document in this new iteration so that we do not process it twice
        results.pop(0)
