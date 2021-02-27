from celery.task import task
from django.conf import settings
from dimagi.utils.web import get_url_base
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.urls import reverse
from corehq.apps.consumer_user.models import ConsumerUserInvitation
from corehq.apps.hqwebapp.tasks import send_html_email_async
from django.utils.http import urlsafe_base64_encode
from django.core.signing import TimestampSigner
from corehq.apps.hqcase.utils import update_case
from django.utils.translation import ugettext_lazy as _
from .const import CONSUMER_INVITATION_SENT
from .const import CONSUMER_INVITATION_STATUS


@task(serializer='pickle', queue=settings.CELERY_MAIN_QUEUE, ignore_result=True)
def create_new_invitation(case_id, domain, opened_by, email):
    invitation = ConsumerUserInvitation.create_invitation(case_id, domain, opened_by, email)
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
        render_to_string('email/registration_email.html', email_context),
        text_content=render_to_string('email/registration_email.txt', email_context)
    )
    update_case(domain, case_id, {CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_SENT})
