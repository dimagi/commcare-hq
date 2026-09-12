from django.template.loader import render_to_string
from django.utils.timesince import timeuntil
from django.utils.translation import gettext as _

from dimagi.utils.web import get_static_url_prefix

from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.short_links.models import ShortLink
from corehq.apps.sms.api import send_sms


MAX_SMS_FORM_NAME_LENGTH = 45


def send_one_time_link(session, form_name):
    if session.email:
        _email_one_time_link(session, form_name)
    else:
        _text_one_time_link(session, form_name)


def _email_one_time_link(session, form_name):
    domain = session.public_webform.domain
    context = {
        'form_name': form_name,
        'url': session.one_time_link,
        'expires_in': timeuntil(session.expires_at),
        'url_prefix': get_static_url_prefix(),
    }
    send_html_email_async.delay(
        _("Your one-time link for {form_name}").format(form_name=form_name),
        session.email,
        render_to_string('public_webforms/email/one_time_link.html', context),
        text_content=render_to_string(
            'public_webforms/email/one_time_link.txt', context
        ),
        domain=domain,
        use_domain_gateway=True,
    )


def _text_one_time_link(session, form_name):
    domain = session.public_webform.domain
    short_link = ShortLink.shorten(domain, session.one_time_link, expires_at=session.expires_at)
    send_sms(
        domain,
        None,  # the respondent is not a contact this project knows
        session.phone_number,
        _("Your one-time link for {form_name}:\n{url}").format(
            form_name=_truncate_for_sms(form_name),
            url=short_link.short_url,
        )
    )


def _truncate_for_sms(form_name):
    if len(form_name) <= MAX_SMS_FORM_NAME_LENGTH:
        return form_name
    return form_name[:MAX_SMS_FORM_NAME_LENGTH - 3] + '...'
