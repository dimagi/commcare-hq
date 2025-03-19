import datetime
import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext

from celery.schedules import crontab

from dimagi.utils.web import get_site_domain, get_static_url_prefix

from corehq.apps.celery import periodic_task, task
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.registration.models import (
    AsyncSignupRequest,
    RegistrationRequest,
)
from corehq.apps.users.models import WebUser


@periodic_task(
    run_every=crontab(minute=0),  # execute once every hour
    queue='background_queue',
)
def activation_24hr_reminder_email():
    """
    Reminds inactive users registered 24 hrs ago to activate their account.
    """
    request_reminders = RegistrationRequest.get_requests_24hrs_ago()

    for request in request_reminders:
        user = WebUser.get_by_username(request.new_user_username)
        registration_link = 'http://' + get_site_domain() + reverse(
            'registration_confirm_domain') + request.activation_guid + '/'
        email_context = {
            "domain": request.domain,
            "registration_link": registration_link,
            "full_name": user.full_name,
            "first_name": user.first_name,
            'url_prefix': get_static_url_prefix(),
        }
        from corehq.apps.registration.utils import project_logo_emails_context
        email_context.update(project_logo_emails_context(request.domain))

        message_plaintext = render_to_string(
            'registration/email/confirm_account_reminder.txt', email_context)
        message_html = render_to_string(
            'registration/email/confirm_account.html', email_context)
        subject = gettext('Reminder to Activate your CommCare project')

        recipient = user.get_email() if user else request.new_user_username
        send_html_email_async.delay(
            subject, recipient, message_html,
            text_content=message_plaintext,
            email_from=settings.DEFAULT_FROM_EMAIL
        )


WIKI_LINK = 'https://wiki.commcarehq.org'
FORUM_LINK = 'https://forum.dimagi.com/'
PRICING_LINK = 'https://www.commcarehq.org/pricing'


@task(queue="email_queue")
def send_domain_registration_email(recipient, domain_name, guid, full_name, first_name):
    registration_link = 'http://' + get_site_domain() + reverse('registration_confirm_domain') + guid + '/'
    params = {
        "domain": domain_name,
        "pricing_link": PRICING_LINK,
        "registration_link": registration_link,
        "full_name": full_name,
        "first_name": first_name,
        "forum_link": FORUM_LINK,
        "wiki_link": WIKI_LINK,
        'url_prefix': get_static_url_prefix(),
    }
    message_plaintext = render_to_string('registration/email/confirm_account.txt', params)
    message_html = render_to_string('registration/email/confirm_account.html', params)

    subject = gettext('Activate your CommCare project')

    try:
        send_html_email_async.delay(subject, recipient, message_html,
                                    text_content=message_plaintext,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message_plaintext)


@periodic_task(
    run_every=crontab(hour=5),  # execute once every day
    queue='background_queue',
)
def delete_old_async_signup_requests():
    """
    This task deletes AsyncSignupRequests that are older than 1 day.
    """
    yesterday = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    AsyncSignupRequest.objects.filter(date_created__lte=yesterday).delete()
