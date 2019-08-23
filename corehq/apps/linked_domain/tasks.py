from __future__ import absolute_import
from __future__ import unicode_literals

from celery.task import task

from corehq.apps.linked_domain.util import pull_missing_multimedia_for_app_and_notify


@task(queue='background_queue')
def pull_missing_multimedia_for_app_and_notify_task(domain, app_id, email=None):
    pull_missing_multimedia_for_app_and_notify(domain, app_id, email)
