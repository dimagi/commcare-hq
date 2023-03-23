from celery.schedules import crontab

from corehq.apps.celery import periodic_task
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import HQApiKey

from datetime import datetime, timedelta

from django.conf import settings
from django.template.loader import render_to_string


@periodic_task(
    run_every=crontab(hour=23, minute=55),
    queue='settings_background_queue',
)
def notify_about_to_expire_api_keys():

    manager = HQApiKey.all_objects

    keys_about_to_expire = manager.all() \
        .filter(is_active=True) \
        .exclude(expiration_date=None) \
        .exclude(expiration_date__lt=datetime.now()) \
        .exclude(expiration_date__gt=datetime.today() + timedelta(days=5))

    for key in keys_about_to_expire:
        params = {
            "key_name": key.name,
        }

        #TODO: check that email is set
        text_content = render_to_string("users/email/about_to_expire_api_key.txt", params)
        html_content = render_to_string("users/email/about_to_expire_api_key.html", params)
        subject = "Api key about to expire"

        send_html_email_async.delay(subject, key.user.email, html_content,
                                    text_content=text_content,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
    pass
