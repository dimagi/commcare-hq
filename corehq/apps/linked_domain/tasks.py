from celery.task import task

from django.conf import settings
from django.utils.translation import ugettext as _

from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.linked_domain.util import (
    pull_missing_multimedia_for_app_and_notify,
)


@task(queue='background_queue')
def pull_missing_multimedia_for_app_and_notify_task(domain, app_id, email=None):
    pull_missing_multimedia_for_app_and_notify(domain, app_id, email)


@task(queue='background_queue')
def push_models(master_domain, models, linked_domains, notify_email):
    # TODO: apps, with update_linked_app
    # TODO: reports, with update_linked_ucr
    # TODO: everything else, with update_model_type
    # TODO: do things in parallel
    # TODO: trap errors
    subject = "Linked project release complete"
    message = _("""
Release complete.

The following content was released:
{}

The following linked domains received this content:
{}
    """).format(
        "\n".join(["- " + m for m in models]),
        "\n".join(["- " + d for d in linked_domains])
    )
    send_mail_async.delay(subject, message, settings.DEFAULT_FROM_EMAIL, [notify_email])
