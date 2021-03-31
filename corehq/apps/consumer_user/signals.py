from casexml.apps.case.const import CASE_INDEX_EXTENSION

from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save

from .const import CONSUMER_INVITATION_CASE_TYPE, CONSUMER_INVITATION_STATUS, CONSUMER_INVITATION_ERROR
from .tasks import handle_consumer_user_invitations


def consumer_user_invitation_case_receiver(sender, case, **kwargs):
    if case.type != CONSUMER_INVITATION_CASE_TYPE:
        return

    email = case.get_case_property('email')
    if not email:
        return

    status = case.get_case_property(CONSUMER_INVITATION_STATUS)
    if status == CONSUMER_INVITATION_ERROR and not case.closed:
        return

    host_indices = [index for index in case.indices if index.relationship == CASE_INDEX_EXTENSION]
    try:
        demographic_case_id = host_indices[0].referenced_id
    except IndexError:
        return

    handle_consumer_user_invitations.delay(
        case.domain, case.case_id, demographic_case_id,
    )


def connect_signals():
    sql_case_post_save.connect(
        consumer_user_invitation_case_receiver,
        CommCareCaseSQL,
        dispatch_uid='consumer_user_invitation_case_receiver',
    )
