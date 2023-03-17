from uuid import uuid4

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.couch import CriticalSection

from corehq.apps.celery import task
from corehq.apps.events.models import (
    get_attendee_case_type,
    ATTENDEE_USER_ID_CASE_PROPERTY,
    AttendeeCase,
)
from corehq.apps.hqcase.utils import submit_case_blocks, bulk_update_cases
from corehq.apps.users.models import CommCareUser


@task(queue='background_queue', ignore_result=True)
def sync_mobile_worker_attendees(domain_name, user_id):
    """
    Create attendees from mobile workers
    """
    with CriticalSection(['sync_mobile_worker_attendees_' + domain_name]):
        new_case_blocks = []
        closed_cases = []
        user_id_case_mapping = get_user_attendee_cases_on_domain(domain_name)
        attendee_case_type = get_attendee_case_type(domain_name)

        for user in CommCareUser.by_domain(domain_name):
            if user.user_id not in user_id_case_mapping:
                new_case_block = get_case_block_for_user(user, user_id, attendee_case_type)
                new_case_blocks.append(new_case_block)
            elif user_id_case_mapping[user.user_id].closed:
                closed_cases.append(user_id_case_mapping[user.user_id])

        submit_case_blocks(
            [cb.as_text() for cb in new_case_blocks],
            domain=domain_name,
            user_id=user_id,
            device_id='corehq.apps.events.tasks.sync_mobile_worker_attendees',
        )
        reopen_cases(closed_cases)


@task(queue='background_queue', ignore_result=True)
def close_mobile_worker_attendee_cases(domain_name):
    """
    Close attendee cases associated with mobile workers
    """
    with CriticalSection(['close_mobile_worker_attendees_' + domain_name]):
        case_changes = []
        user_id_case_mapping = get_user_attendee_cases_on_domain(domain_name)
        mobile_worker_user_ids = {user.user_id for user in CommCareUser.by_domain(domain_name)}

        for commcare_user_id, case in user_id_case_mapping.items():
            if commcare_user_id in mobile_worker_user_ids:
                case_changes.append((case.case_id, {}, True))

        if case_changes:
            bulk_update_cases(
                domain_name,
                case_changes,
                device_id='corehq.apps.events.tasks.close_mobile_worker_attendee_cases'
            )


def get_user_attendee_cases_on_domain(domain):
    """Returns a mapping like `{user_id1: case1, user_id2: case2}`. The user_ids's are fetched from the case's
    `ATTENDEE_USER_ID_CASE_PROPERTY` property, which is a commcare user id
    """
    cases = AttendeeCase.objects.by_domain(domain, include_closed=True)
    return {c.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY): c for c in cases}


def get_case_block_for_user(user, owner_id, attendee_case_type):
    case_name = ' '.join((user.first_name, user.last_name))
    fields = {
        ATTENDEE_USER_ID_CASE_PROPERTY: user.user_id,
    }
    return CaseBlock(
        create=True,
        case_id=uuid4().hex,
        owner_id=owner_id,
        case_type=attendee_case_type,
        case_name=case_name,
        update=fields,
    )

def reopen_cases(cases):
    for case in cases:
        transactions = case.get_closing_transactions()
        for transaction in transactions:
            transaction.form.archive()
