import datetime
import uuid
from xml.etree import ElementTree
from couchdbkit import ResourceNotFound
from dimagi.utils.couch.database import iter_docs
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from dimagi.utils.parsing import json_format_datetime
from django.template.loader import render_to_string
from casexml.apps.case.xml import V2
from casexml.apps.phone.caselogic import get_related_cases
from corehq.apps.hqcase.exceptions import CaseAssignmentError

from receiver.util import spoof_submission

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


def get_case_ids_in_domain(domain, type=None):
    type_key = [type] if type else []
    return [res['id'] for res in CommCareCase.get_db().view('hqcase/types_by_domain',
        startkey=[domain] + type_key,
        endkey=[domain] + type_key + [{}],
        reduce=False,
        include_docs=False,
    )]


def get_cases_in_domain(domain, type=None):
    return (CommCareCase.wrap(doc) for doc in iter_docs(CommCareCase.get_db(),
                                                        get_case_ids_in_domain(domain, type=type)))

def assign_case(case_or_case_id, owner_id, acting_user=None, include_subcases=True,
                include_parent_cases=False, exclude=()):
    """
    Assigns a case to an owner. Optionally traverses through subcases and parent cases
    and reassigns those to the same owner.
    """
    if isinstance(case_or_case_id, basestring):
        primary_case = CommCareCase.get(case_or_case_id)
    else:
        primary_case = case_or_case_id
    cases_to_assign = [primary_case]
    if include_subcases:
        cases_to_assign.extend(get_related_cases([primary_case], primary_case.domain, search_up=False).values())
    if include_parent_cases:
        cases_to_assign.extend(get_related_cases([primary_case], primary_case.domain, search_up=True).values())
    if exclude:
        cases_to_assign = filter(lambda case: case._id not in exclude, cases_to_assign)
    return assign_cases(cases_to_assign, owner_id, acting_user)


def assign_cases(caselist, owner_id, acting_user=None):
    """
    Assign all cases in a list to an owner. Won't update if the owner is already
    set on the case. Doesn't touch parent cases or subcases.

    Returns the list of ids of cases that were reassigned.
    """
    if not caselist:
        return

    def _assert(bool, msg):
        if not bool:
            raise CaseAssignmentError(msg)

    from corehq.apps.users.cases import get_wrapped_owner
    # "security"
    unique_domains = set([c.domain for c in caselist])
    _assert(len(unique_domains) == 1, 'case list had cases spanning multiple domains')
    [domain] = unique_domains
    _assert(domain, 'domain for cases was empty')
    owner = get_wrapped_owner(owner_id)
    _assert(owner, 'no owner with id "%s" found' % owner_id)
    _assert(owner.domain == domain, 'owner was not in domain %s for cases' % domain)

    username = acting_user.username if acting_user else 'system'
    user_id = acting_user._id if acting_user else 'system'
    filtered_cases = set([c for c in caselist if c.owner_id != owner_id])
    if filtered_cases:
        caseblocks = [ElementTree.tostring(CaseBlock(
                create=False,
                case_id=c._id,
                owner_id=owner_id,
                version=V2,
            ).as_xml(format_datetime=json_format_datetime)) for c in filtered_cases
        ]
        # todo: this should check whether the submit_case_blocks call actually succeeds
        submit_case_blocks(caseblocks, domain, username=username,
                           user_id=user_id)

    return [c._id for c in filtered_cases]
