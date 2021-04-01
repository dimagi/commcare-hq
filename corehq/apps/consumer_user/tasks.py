from datetime import datetime, timedelta
from collections import defaultdict

from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from celery.schedules import crontab
from celery.task import periodic_task, task

from corehq.apps.consumer_user.models import (
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)
from corehq.apps.hqcase.utils import update_case, bulk_update_cases
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.view_utils import absolute_reverse

from .const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_ERROR,
    CONSUMER_INVITATION_SENT,
    CONSUMER_INVITATION_STATUS,
)


@task
def handle_consumer_user_invitations(domain, invitation_case_id, demographic_case_id):
    invitation_case = CaseAccessors(domain).get_case(invitation_case_id)
    email = invitation_case.get_case_property('email')
    status = invitation_case.get_case_property(CONSUMER_INVITATION_STATUS)
    keep_open_status = [CONSUMER_INVITATION_SENT, CONSUMER_INVITATION_ACCEPTED]

    if not invitation_case.closed and ConsumerUserInvitation.objects.filter(
        demographic_case_id=demographic_case_id, active=True, accepted=False
    ).exclude(case_id=invitation_case_id).exists():
        # If there is currently an open, unaccepted invitation for the same demographic case, do nothing
        update_case(
            domain=domain,
            case_id=invitation_case_id,
            case_properties={
                CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_ERROR,
                CONSUMER_INVITATION_ERROR: "There is already an open invitation for this case",
            },
            device_id=__name__ + '.handle_consumer_user_invitations',
        )
        return

    try:
        invitation = ConsumerUserInvitation.objects.get(
            case_id=invitation_case_id,
            domain=domain,
            demographic_case_id=demographic_case_id,
            active=True,
        )
        if invitation.email == email and status in keep_open_status and not invitation_case.closed:
            # An invitation has already been sent to this address, and this invite has been created, so do nothing
            return
        # For any other requests, we'll make a new invitation so we can keep track. Deactivate this one.
        invitation.make_inactive()
    except ConsumerUserInvitation.DoesNotExist:
        pass

    if invitation_case.closed:
        # There is nothing left to do.
        return

    if ConsumerUserCaseRelationship.objects.filter(case_id=demographic_case_id, domain=domain).exists():
        # There is already a relationship with this case_id, so don't invite anyone new
        update_case(
            domain=domain,
            case_id=invitation_case_id,
            case_properties={
                CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_ERROR,
                CONSUMER_INVITATION_ERROR: "Someone else has already created a user for this case."
            },
            device_id=__name__ + '.handle_consumer_user_invitations',
        )
        return

    # Make a new invitation, and send an email to the user
    new_invitation = ConsumerUserInvitation.objects.create(
        case_id=invitation_case_id,
        domain=domain,
        demographic_case_id=demographic_case_id,
        invited_by=invitation_case.opened_by,
        email=email,
    )
    email_context = {
        'link':
            absolute_reverse(
                'consumer_user:consumer_user_register',
                kwargs={'signed_invitation_id': new_invitation.signature()},
            ),
    }
    send_html_email_async.delay(
        _('Beneficiary Registration'),
        email,
        render_to_string('consumer_user/email/registration_email.html', email_context),
        text_content=render_to_string('consumer_user/email/registration_email.txt', email_context)
    )

    update_case(
        domain=domain,
        case_id=invitation_case_id,
        case_properties={
            CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_SENT,
            CONSUMER_INVITATION_ERROR: "",
        },
        device_id=__name__ + '.handle_consumer_user_invitations',
    )


@periodic_task(run_every=crontab(hour="3", minute="0", day_of_week="*"), queue='background_queue')
def expire_unused_invitations():
    expired_invitations = ConsumerUserInvitation.objects.filter(
        active=True,
        accepted=False,
        invited_on__lt=datetime.utcnow() - timedelta(days=30),
    )

    invitation_case_ids = expired_invitations.values_list('domain', 'case_id')
    domain_mapped_case_ids = defaultdict(list)
    for domain, case_id in invitation_case_ids:
        domain_mapped_case_ids[domain].append(case_id)

    for domain, case_ids in domain_mapped_case_ids.items():
        case_changes = [(case_id, {CONSUMER_INVITATION_STATUS: "expired"}, True) for case_id in case_ids]
        bulk_update_cases(domain, case_changes, device_id=__name__ + '.expire_unused_invitations')

    expired_invitations.update(active=False)
