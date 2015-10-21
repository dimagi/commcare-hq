from corehq.apps.users.models import CouchUser
from corehq.elastic import get_es
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormError
from dimagi.utils.couch.database import iter_docs


def iter_problem_forms(domain, since=None):
    problem_ids = get_form_ids_by_type(domain, 'XFormError', start=since)
    for doc in iter_docs(XFormError.get_db(), problem_ids):
        yield XFormError.wrap(doc)
