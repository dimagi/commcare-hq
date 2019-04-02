from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from celery.schedules import crontab
from celery.task import periodic_task, task
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from django.utils.translation import ugettext

from dimagi.utils.web import get_site_domain

from corehq.apps.registration.models import RegistrationRequest
from corehq.apps.users.models import WebUser
from corehq.apps.hqwebapp.tasks import send_html_email_async


@periodic_task(
    run_every=crontab(minute=0),  # execute once every hour
    queue='background_queue',
)
def activation_24hr_reminder_email():
    """
    Reminds inactive users registered 24 hrs ago to activate their account.
    """
    request_reminders = RegistrationRequest.get_requests_24hrs_ago()

    DNS_name = get_site_domain()

    for request in request_reminders:
        user = WebUser.get_by_username(request.new_user_username)
        registration_link = 'http://' + DNS_name + reverse(
            'registration_confirm_domain') + request.activation_guid + '/'
        email_context = {
            "domain": request.domain,
            "registration_link": registration_link,
            "full_name": user.full_name,
            "first_name": user.first_name,
            'url_prefix': '' if settings.STATIC_CDN else 'http://' + DNS_name,
        }

        message_plaintext = render_to_string(
            'registration/email/confirm_account_reminder.txt', email_context)
        message_html = render_to_string(
            'registration/email/confirm_account.html', email_context)
        subject = ugettext('Reminder to Activate your CommCare project')

        send_html_email_async.delay(
            subject, request.new_user_username, message_html,
            text_content=message_plaintext,
            email_from=settings.DEFAULT_FROM_EMAIL
        )


WIKI_LINK = 'https://wiki.commcarehq.org'
FORUM_LINK = 'https://forum.dimagi.com/'
PRICING_LINK = 'https://www.commcarehq.org/pricing'


@task(serializer='pickle', queue="email_queue")
def send_domain_registration_email(recipient, domain_name, guid, full_name, first_name):
    DNS_name = get_site_domain()
    registration_link = 'http://' + DNS_name + reverse('registration_confirm_domain') + guid + '/'
    params = {
        "domain": domain_name,
        "pricing_link": PRICING_LINK,
        "registration_link": registration_link,
        "full_name": full_name,
        "first_name": first_name,
        "forum_link": FORUM_LINK,
        "wiki_link": WIKI_LINK,
        'url_prefix': '' if settings.STATIC_CDN else 'http://' + DNS_name,
    }
    message_plaintext = render_to_string('registration/email/confirm_account.txt', params)
    message_html = render_to_string('registration/email/confirm_account.html', params)

    subject = ugettext('Activate your CommCare project')

    try:
        send_html_email_async.delay(subject, recipient, message_html,
                                    text_content=message_plaintext,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message_plaintext)
