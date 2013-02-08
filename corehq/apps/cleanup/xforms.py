from casexml.apps.case.signals import process_cases
from couchforms.models import XFormError
from dimagi.utils.couch.database import iter_docs


def get_problem_ids(domain, since=None):
    startkey = [domain, "by_type", "XFormError"]
    endkey = startkey + [{}]
    if since:
        startkey.append(since.isoformat())

    return [row['id'] for row in XFormError.get_db().view(
        "receiverwrapper/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False
    )]

def iter_problem_forms(domain, since=None):
    for doc in iter_docs(XFormError.get_db(), get_problem_ids(domain, since)):
        yield XFormError.wrap(doc)

def reprocess_form_cases(form):
    """
    For a given form, reprocess all case elements inside it. This operation
    should be a no-op if the form was sucessfully processed, but should
    correctly inject the update into the case history if the form was NOT
    successfully processed.
    """
    process_cases(None, form, reconcile=True)
