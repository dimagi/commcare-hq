from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from corehq.apps.hqwebapp.tasks import send_html_email_async


def send_invitation_email(registry, invitation):
    subject = _("Data Registry Invitation from {domain}").format(registry.domain)
    context = {
        'domain': invitation.domain,
        'owning_domain': registry.domain,
        'registry_url': reverse('manage_registry', args=[invitation.domain, registry.slug])
    }

    contact_email = ''
    email_html = render_to_string('registry/email/invitation.html', context)
    email_plaintext = render_to_string('registry/email/invitation.txt', context)
    send_html_email_async.delay(
        subject, contact_email, email_html,
        text_content=email_plaintext,
    )
