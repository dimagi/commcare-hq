from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save

from .const import CONSUMER_INVITATION_CASE_TYPE
from .tasks import create_new_consumer_user_invitation
from casexml.apps.case.const import CASE_INDEX_EXTENSION
from .const import CONSUMER_INVITATION_STATUS


def send_email_case_changed_receiver(sender, case, **kwargs):
    if case.type != CONSUMER_INVITATION_CASE_TYPE:
        return
    email = case.get_case_property('email')
    if not email:
        return
    host_indices = [index for index in case.indices if index.relationship == CASE_INDEX_EXTENSION]
    try:
        demographic_case_id = host_indices[0].referenced_id
    except IndexError:
        return

    create_new_consumer_user_invitation.delay(case.domain, case.case_id,
                                              demographic_case_id, case.closed,
                                              case.get_case_property(CONSUMER_INVITATION_STATUS),
                                              case.opened_by, email)


def connect_signals():
    sql_case_post_save.connect(
        send_email_case_changed_receiver,
        CommCareCaseSQL,
        dispatch_uid='send_email_case_changed_receiver'
    )
