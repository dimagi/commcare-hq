from dimagi.utils.logging import notify_exception
from dimagi.utils.web import get_site_domain
from django.db.utils import IntegrityError
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.urls import reverse
from corehq.apps.consumer_user.models import ConsumerUserInvitation
from corehq.apps.consumer_user.models import ConsumerUserCaseRelationship
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save
from corehq.apps.hqwebapp.tasks import send_html_email_async
from django.utils.http import urlsafe_base64_encode
from django.core.signing import TimestampSigner


def send_email_case_changed_receiver(sender, case, **kwargs):
    try:
        if case.type != 'commcare-caseuserinvitation':
            return
        try:
            email = case.get_case_property('email')
        except IntegrityError:
            email = 'challarao@beehyv.com'
        invitation, created = ConsumerUserInvitation.objects.get_or_create(case_id=case.case_id,
                                                                           domain=case.domain)
        if created or invitation.email != email:
            invitation.invited_by = case.opened_by
            invitation.email = email
            invitation.accepted = False
            invitation.save()
            if not created:
                ConsumerUserCaseRelationship.objects.filter(case_id=case.case_id,
                                                            domain=case.domain).delete()
            # Change to https after the discussion
            url = 'http://%s%s' % (get_site_domain(),
                                    reverse('consumer_user:patient_register',
                                            kwargs={
                                                'invitation': TimestampSigner().sign(urlsafe_base64_encode(
                                                    force_bytes(invitation.pk)
                                                ))
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
