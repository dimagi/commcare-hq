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
        'registry_name': registry.name,
        'registry_url': reverse('manage_registry', args=[invitation.domain, registry.slug], absolute=True)
    }

    _send_registry_email(invitation.domain, subject, 'invitation', context)


def send_invitation_response_email(registry, invitation):
    if invitation.status == RegistryInvitation.STATUS_ACCEPTED:
        subject = _("CommCare Data Registry: Participant opted in")
    else:
        subject = _("CommCare Data Registry: Participant opted out")

    context = {
        'invitation': invitation,
        'domain': invitation.domain,
        'owning_domain': registry.domain,
        'registry_name': registry.name,
        'registry_url': reverse('manage_registry', args=[registry.domain, registry.slug], absolute=True)
    }

    _send_registry_email(registry.domain, subject, 'invitation_response', context)


def send_grant_email(registry, from_domain, to_domains):
    subject = _("CommCare Data Registry: Access Granted")
    for domain in to_domains:
        context = {
            'domain': domain,
            'access_domain': from_domain,
            'owning_domain': registry.domain,
            'registry_name': registry.name,
            'registry_url': reverse('manage_registry', args=[domain, registry.slug], absolute=True)
        }

        _send_registry_email(domain, subject, 'access_granted', context)


def _send_registry_email(for_domain, subject, template, context):
    recipients = {u.get_email() for u in WebUser.get_admins_by_domain(for_domain)}
    email_html = render_to_string(f'registry/email/{template}.html', context)
    email_plaintext = render_to_string(f'registry/email/{template}.txt', context)
    send_html_email_async.delay(
        subject, recipients, email_html,
        text_content=email_plaintext,
        domain=for_domain,
        use_domain_gateway=True,
    )
