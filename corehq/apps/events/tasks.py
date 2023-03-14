from uuid import uuid4

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.couch import CriticalSection

from corehq.apps.celery import task
from corehq.apps.events.models import (
    ATTENDEE_CASE_TYPE,
    ATTENDEE_USER_ID_CASE_PROPERTY,
    AttendeeCase,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase


@task(queue='background_queue', ignore_result=True)
def sync_mobile_worker_attendees(domain_name, user_id):
    """
    Create attendees from mobile workers

    ``user_id`` is the user ID of ``request.couch_user``.
    """
    with CriticalSection(['sync_attendees_' + domain_name]):
        case_blocks = []
        closed_cases = []
        existing = get_existing_cases_by_user_ids(domain_name)

        for user in CommCareUser.by_domain(domain_name):
            if user.user_id not in existing:
                case_blocks.append(get_case_block_for_user(user, user_id))
            elif existing[user.user_id].closed:
                closed_cases.append(existing[user.user_id])

        submit_case_blocks(
            [cb.as_text() for cb in case_blocks],
            domain=domain_name,
            user_id=user_id,
            device_id=__name__,
        )
        reopen_cases(closed_cases)


def get_existing_cases_by_user_ids(domain: str) -> dict[str, CommCareCase]:
    cases = AttendeeCase.objects.by_domain(domain, include_closed=True)
    return {c.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY): c for c in cases}


# TODO: Test
def get_case_block_for_user(user: CommCareUser, owner_id: str) -> CaseBlock:
    case_name = ' '.join((user.first_name, user.last_name))
    fields = {
        ATTENDEE_USER_ID_CASE_PROPERTY: user.user_id,
    }
    return CaseBlock(
        create=True,
        case_id=uuid4().hex,
        owner_id=owner_id,
        case_type=ATTENDEE_CASE_TYPE,
        case_name=case_name,
        update=fields,
    )


# TODO: Test
def reopen_cases(cases):
    for case in cases:
        transactions = case.get_closing_transactions()
        for transaction in transactions:
            transaction.form.archive()
