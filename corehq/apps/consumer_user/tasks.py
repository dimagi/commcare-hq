from django.core.signing import TimestampSigner
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import ugettext_lazy as _

from celery.task import task

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from dimagi.utils.web import get_url_base

from corehq.apps.consumer_user.models import (
    ConsumerUserCaseRelationship,
    ConsumerUserInvitation,
)
from corehq.apps.hqcase.utils import update_case
from corehq.apps.hqwebapp.tasks import send_html_email_async

from .const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_SENT,
    CONSUMER_INVITATION_STATUS,
)


@task
def create_new_invitation(case):
    email = case.get_case_property('email')
    status = case.get_case_property(CONSUMER_INVITATION_STATUS)
    case_id = case.case_id
    domain = case.domain
    opened_by = case.opened_by
    host_indices = [index for index in case.indices if index.relationship == CASE_INDEX_EXTENSION]
    try:
        demographic_case_id = host_indices[0].referenced_id
    except IndexError:
        return

    invitation = ConsumerUserInvitation.objects.filter(case_id=case_id,
                                                       domain=domain,
                                                       demographic_case_id=demographic_case_id,
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
        if ConsumerUserCaseRelationship.objects.filter(case_id=demographic_case_id,
                                                       domain=domain).exists():
            return
    invitation = ConsumerUserInvitation.create_invitation(case_id, domain, demographic_case_id, opened_by, email)
    url = '%s%s' % (get_url_base(),
                    reverse('consumer_user:consumer_user_register',
                            kwargs={
                                'invitation': TimestampSigner().sign(urlsafe_base64_encode(
                                    force_bytes(invitation.pk)
                                ))
                            }))
    email_context = {
        'link': url,
    }
    send_html_email_async.delay(
        _('Beneficiary Registration'),
        email,
        render_to_string('consumer_user/email/registration_email.html', email_context),
        text_content=render_to_string('consumer_user/email/registration_email.txt', email_context)
    )
    update_case(domain, case_id, {CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_SENT})
