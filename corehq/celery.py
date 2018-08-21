from __future__ import absolute_import, unicode_literals

from django.conf import settings

from celery import Celery

app = Celery('commcare-hq')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
