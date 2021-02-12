from dimagi.utils.logging import notify_exception
from dimagi.utils.web import get_site_domain
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.urls import reverse
from corehq.apps.consumer_user.models import ConsumerUserInvitation
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save
from corehq.apps.hqwebapp.tasks import send_html_email_async
from django.utils.http import urlsafe_base64_encode


def send_email_case_changed_receiver(sender, case, **kwargs):
    try:
        email = 'challarao@beehyv.com'

        invitation, created = ConsumerUserInvitation.objects.get_or_create(case_id=case.case_id,
                                                                           domain=case.domain)
        if created or invitation.email != email:
            invitation.invited_by = case.opened_by
            invitation.invited_on = case.opened_on
            invitation.email = email
            invitation.save()
            url = 'https://%s%s' % (get_site_domain(),
                                    reverse('consumer_user:patient_register',
                                            kwargs={
                                                'invitation': urlsafe_base64_encode(
                                                    force_bytes(invitation.pk)
                                                )
                                            }))
            email_context = {
                'link': url,
            }
            send_html_email_async.delay(
                'Beneficiary Registration',
                email,
                render_to_string('email/registration_email.html', email_context),
                text_content=render_to_string('email/registration_email.txt', email_context)
            )

    except Exception:
        notify_exception(
            None,
            message="Could not create messaging case changed task. Is RabbitMQ running?"
        )


def connect_signals():
    sql_case_post_save.connect(
        send_email_case_changed_receiver,
        CommCareCaseSQL,
        dispatch_uid='send_email_case_changed_receiver'
    )
