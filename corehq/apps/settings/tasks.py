from celery.schedules import crontab

from corehq.apps.celery import periodic_task
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.settings.views import ApiKeyView
from corehq.apps.users.models import HQApiKey
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.timezones.conversions import ServerTime
from corehq.util.view_utils import absolute_reverse

from datetime import datetime, timedelta

from django.template.loader import render_to_string

import pytz


def _to_utc(value):
    return (ServerTime(value)
            .user_time(pytz.timezone('UTC'))
            .done()
            .strftime(USER_DATETIME_FORMAT)) if value else '-'


@periodic_task(
    run_every=crontab(hour=23, minute=0),
    queue='background_queue',
)
def notify_about_to_expire_api_keys():

    manager = HQApiKey.all_objects

    keys_about_to_expire = manager.all() \
        .filter(is_active=True) \
        .exclude(expiration_date=None) \
        .exclude(expiration_date__lt=datetime.now()) \
        .exclude(expiration_date__gt=datetime.today() + timedelta(days=5))

    url = absolute_reverse(ApiKeyView.urlname)

    for key in keys_about_to_expire:
        params = {
            "key_name": key.name,
            "last_used": _to_utc(key.last_used),
            "expiration_date": _to_utc(key.expiration_date),
            "url": url,
        }

        text_content = render_to_string("settings/email/about_to_expire_api_key.txt", params)
        html_content = render_to_string("settings/email/about_to_expire_api_key.html", params)
        subject = "Api key about to expire"

        send_html_email_async.delay(subject, key.user.email, html_content,
                                    text_content=text_content,
                                    domain=key.domain,
                                    use_domain_gateway=True)
