from corehq.apps.consumer_user.models import ConsumerUserInvitation
from corehq.apps.consumer_user.models import ConsumerUserCaseRelationship
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save
from .const import CONSUMER_INVITATION_CASE_TYPE
from .tasks import create_new_invitation


def make_invitation_inactive(invitation, case):
    invitation.make_inactive()
    ConsumerUserCaseRelationship.objects.filter(case_id=case.case_id,
                                                domain=case.domain).delete()


def send_email_case_changed_receiver(sender, case, **kwargs):
    if case.type != CONSUMER_INVITATION_CASE_TYPE:
        return
    email = case.get_case_property('email')
    invitation = ConsumerUserInvitation.objects.filter(case_id=case.case_id,
                                                       domain=case.domain,
                                                       active=True).last()
    if case.closed:
        if invitation:
            make_invitation_inactive(invitation, case)
        return
    elif invitation and email == invitation.email:
        return
    elif invitation:
        make_invitation_inactive(invitation, case)
    create_new_invitation.delay(case.case_id, case.domain, case.opened_by, email)


def connect_signals():
    sql_case_post_save.connect(
        send_email_case_changed_receiver,
        CommCareCaseSQL,
        dispatch_uid='send_email_case_changed_receiver'
    )
