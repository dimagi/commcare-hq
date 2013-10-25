import datetime
import uuid
from couchdbkit import ResourceNotFound
from dimagi.utils.couch.database import iter_docs
from casexml.apps.case.models import CommCareCase
from dimagi.utils.parsing import json_format_datetime
from django.template.loader import render_to_string

from receiver.util import spoof_submission

from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.util import get_submit_url

ALLOWED_CASE_IDENTIFIER_TYPES = [
    "contact_phone_number",
    "external_id",
]


def submit_case_blocks(case_blocks, domain, username="system", user_id="",
                       xmlns='http://commcarehq.org/case'):
    now = json_format_datetime(datetime.datetime.utcnow())
    if not isinstance(case_blocks, basestring):
        case_blocks = ''.join(case_blocks)
    form_xml = render_to_string('hqcase/xml/case_block.xml', {
        'xmlns': xmlns,
        'case_block': case_blocks,
        'time': now,
        'uid': uuid.uuid4().hex,
        'username': username,
        'user_id': user_id,
    })
    spoof_submission(
        get_submit_url(domain),
        form_xml,
        hqsubmission=False,
    )


def get_case_wrapper(data):
    from corehq.apps.commtrack.models import get_case_wrapper as commtrack_wrapper
    def pact_wrapper(data):
        if data['domain'] == 'pact' and data['type'] == 'cc_path_client':
            from pact.models import PactPatientCase
            return PactPatientCase

    wrapper_funcs = [pact_wrapper, commtrack_wrapper]

    wrapper = None
    for wf in wrapper_funcs:
        wrapper = wf(data)
        if wrapper is not None:
            break
    return wrapper


def get_case_by_domain_hq_user_id(domain, user_id, include_docs=False):
    """
    Get the 'user case' for user_id. User cases are part of the call center feature.
    """
    return CommCareCase.view('hqcase/by_domain_hq_user_id',
                         key=[domain, user_id],
                         reduce=False,
                         include_docs=include_docs).one()


def get_case_by_identifier(domain, identifier):
    # circular import
    from corehq.apps.api.es import CaseES
    case_es = CaseES(domain)

    def _query_by_type(i_type):
        q = case_es.base_query(
            terms={
                i_type: identifier,
            },
            fields=['_id', i_type],
            size=1
        )
        response = case_es.run_query(q)
        raw_docs = response['hits']['hits']
        if raw_docs:
            return CommCareCase.get(raw_docs[0]['_id'])

    # Try by any of the allowed identifiers
    for identifier_type in ALLOWED_CASE_IDENTIFIER_TYPES:
        case = _query_by_type(identifier_type)
        if case is not None:
            return case

    # Try by case id
    try:
        case_by_id = CommCareCase.get(identifier)
        if case_by_id.domain == domain:
            return case_by_id
    except (ResourceNotFound, KeyError):
        pass

    return None


def get_case_ids_in_domain(domain):
    return [res['id'] for res in CommCareCase.get_db().view('hqcase/by_domain_external_id',
        startkey=[domain],
        endkey=[domain, {}],
        reduce=False,
        include_docs=False,
    )]


def get_cases_in_domain(domain):
    return (CommCareCase.wrap(doc) for doc in iter_docs(CommCareCase.get_db(),
                                                        get_case_ids_in_domain(domain)))
