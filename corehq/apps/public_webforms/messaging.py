from django.template.loader import render_to_string
from django.utils.timesince import timeuntil
from django.utils.translation import gettext as _

from dimagi.utils.web import get_static_url_prefix

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.sms.api import send_sms


def send_one_time_link(session, form_name):
    if session.email:
        _email_one_time_link(session, form_name)
    else:
        _text_one_time_link(session, form_name)


def _one_time_link(session):
    # TODO: implement real public link handling, at this url or otherwise
    return f'{session.public_webform.public_url}{session.id.hex}/'


def _email_one_time_link(session, form_name):
    domain = session.public_webform.domain
    context = {
        'form_name': form_name,
        'project_name': Domain.get_by_name(domain).display_name(),
        'url': _one_time_link(session),
        # what is left of this session, which for a re-sent link is less than
        # a full lifespan
        'expires_in': timeuntil(session.expires_at),
        # the base email template loads its images from here
        'url_prefix': get_static_url_prefix(),
    }
    send_html_email_async.delay(
        _("Your one-time link for {form_name}").format(form_name=form_name),
        session.email,
        render_to_string('public_webforms/email/one_time_link.html', context),
        text_content=render_to_string(
            'public_webforms/email/one_time_link.txt', context),
        domain=domain,
        use_domain_gateway=True,
    )


def _text_one_time_link(session, form_name):
    send_sms(
        session.public_webform.domain,
        None,  # the respondent is not a contact this project knows
        session.phone_number,
        _("Your one-time link for {form_name} is: {url}").format(
            form_name=form_name, url=_one_time_link(session)),
    )
