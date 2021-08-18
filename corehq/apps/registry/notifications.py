from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.registry.models import RegistryInvitation
from corehq.apps.users.models import WebUser
from corehq.util import reverse


def send_invitation_email(registry, invitation):
    subject = _("CommCare Data Registry: Invitation to participate")
    context = {
        'domain': invitation.domain,
        'owning_domain': registry.domain,
        'registry_url': reverse('manage_registry', args=[invitation.domain, registry.slug], absolute=True)
    }

    _send_registry_email(invitation.domain, subject, 'invitation', context)


def send_invitation_response_email(registry, invitation):
    if invitation.status == RegistryInvitation.STATUS_ACCEPTED:
        subject = _("CommCare Data Registry: Participant opted in")
    else:
        subject = _("CommCare Data Registry: Participant opted out")

    context = {
        'domain': invitation.domain,
        'owning_domain': registry.domain,
        'registry_url': reverse('manage_registry', args=[invitation.domain, registry.slug], absolute=True)
    }

    _send_registry_email(registry.domain, subject, 'invitation_response', context)


def _send_registry_email(for_domain, subject, template, context):
    recipients = {u.get_email() for u in WebUser.get_admins_by_domain(for_domain)}
    email_html = render_to_string(f'registry/email/{template}.html', context)
    email_plaintext = render_to_string(f'registry/email/{template}.txt', context)
    send_html_email_async.delay(
        subject, recipients, email_html,
        text_content=email_plaintext,
    )
