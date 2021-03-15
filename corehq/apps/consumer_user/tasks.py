from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from celery.task import task

from corehq.apps.consumer_user.models import (
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)
from corehq.apps.hqcase.utils import update_case
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.util.view_utils import absolute_reverse

from .const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_SENT,
    CONSUMER_INVITATION_STATUS,
)


@task
def create_new_consumer_user_invitation(domain, case_id, demographic_case_id, closed, status, opened_by, email):

    invitation = ConsumerUserInvitation.objects.filter(
        case_id=case_id,
        domain=domain,
        demographic_case_id=demographic_case_id,
        active=True,
    ).last()
    is_status_sent_or_accepted = status == CONSUMER_INVITATION_SENT or status == CONSUMER_INVITATION_ACCEPTED
    if closed:
        if invitation:
            invitation.make_inactive()
        return
    elif invitation and email == invitation.email and is_status_sent_or_accepted:
        return
    elif invitation:
        invitation.make_inactive()
        if ConsumerUserCaseRelationship.objects.filter(case_id=demographic_case_id, domain=domain).exists():
            return
    invitation = ConsumerUserInvitation.create_invitation(case_id, domain, demographic_case_id, opened_by, email)
    email_context = {
        'link': absolute_reverse(
            'consumer_user:consumer_user_register',
            kwargs={'invitation': invitation.signature()},
        ),
    }
    send_html_email_async.delay(
        _('Beneficiary Registration'),
        email,
        render_to_string('consumer_user/email/registration_email.html', email_context),
        text_content=render_to_string('consumer_user/email/registration_email.txt', email_context)
    )
    update_case(domain, case_id, {CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_SENT})
