from corehq.apps.consumer_user.models import (
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save

from .const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_CASE_TYPE,
    CONSUMER_INVITATION_SENT,
    CONSUMER_INVITATION_STATUS,
)
from .tasks import create_new_invitation


def send_email_case_changed_receiver(sender, case, **kwargs):
    if case.type != CONSUMER_INVITATION_CASE_TYPE:
        return
    email = case.get_case_property('email')
    status = case.get_case_property(CONSUMER_INVITATION_STATUS)
    invitation = ConsumerUserInvitation.objects.filter(case_id=case.case_id,
                                                       domain=case.domain,
                                                       active=True).last()
    is_status_sent_or_accepted = status == CONSUMER_INVITATION_SENT or status == CONSUMER_INVITATION_ACCEPTED
    if case.closed:
        if invitation:
            invitation.make_inactive()
        return
    elif invitation and email == invitation.email and is_status_sent_or_accepted:
        return
    elif invitation:
        invitation.make_inactive()
        if ConsumerUserCaseRelationship.objects.filter(case_id=case.case_id,
                                                       domain=case.domain).exists():
            return
    create_new_invitation.delay(case.case_id, case.domain, case.opened_by, email)


def connect_signals():
    sql_case_post_save.connect(
        send_email_case_changed_receiver,
        CommCareCaseSQL,
        dispatch_uid='send_email_case_changed_receiver'
    )
