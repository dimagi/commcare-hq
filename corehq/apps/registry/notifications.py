from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser


def send_invitation_email(registry, invitation):
    subject = _("Invitation to participate in a CommCare Data Registry")
    context = {
        'domain': invitation.domain,
        'owning_domain': registry.domain,
        'registry_url': reverse('manage_registry', args=[invitation.domain, registry.slug])
    }

    recipients = {u.get_email() for u in WebUser.get_admins_by_domain(invitation.domain)}
    email_html = render_to_string('registry/email/invitation.html', context)
    email_plaintext = render_to_string('registry/email/invitation.txt', context)
    send_html_email_async.delay(
        subject, recipients, email_html,
        text_content=email_plaintext,
    )
