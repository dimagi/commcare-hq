from collections import namedtuple
from datetime import datetime

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q

import architect
from oauth2_provider.settings import APPLICATION_MODEL

from corehq.sql_db.fields import CharIdField
from corehq.util.markup import mark_up_urls
from corehq.util.models import ForeignValue, foreign_init
from corehq.util.quickcache import quickcache

PageInfoContext = namedtuple('PageInfoContext', 'title url')


class GaTracker(namedtuple('GaTracking', 'category action label')):
    """
    Info for tracking clicks using Google Analytics
    see https://developers.google.com/analytics/devguides/collection/analyticsjs/events
    """
    def __new__(cls, category, action, label=None):
        return super(GaTracker, cls).__new__(cls, category, action, label)


class Alert(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=False)

    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    timezone = models.CharField(max_length=32, default='UTC')

    text = models.TextField()
    domains = ArrayField(models.CharField(max_length=126), null=True)
    created_by_domain = CharIdField(max_length=255, null=True, db_index=True)
    created_by_user = CharIdField(max_length=128, null=True)

    class Meta(object):
        app_label = 'hqwebapp'
        db_table = 'hqwebapp_maintenancealert'

    @property
    def html(self):
        return mark_up_urls(self.text)

    def save(self, *args, **kwargs):
        cls = type(self)
        cls.get_active_alerts.clear(cls)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        cls = type(self)
        cls.get_active_alerts.clear(cls)
        super().delete(*args, **kwargs)

    @classmethod
    @quickcache([], timeout=1 * 60)
    def get_active_alerts(cls):
        # return active HQ alerts
        now = datetime.utcnow()
        active_alerts = cls.objects.filter(
            Q(active=True),
            Q(start_time__lte=now) | Q(start_time__isnull=True),
            Q(end_time__gt=now) | Q(end_time__isnull=True)
        )
        return active_alerts.order_by('-modified')


class UserAgent(models.Model):
    MAX_LENGTH = 255

    value = models.CharField(max_length=MAX_LENGTH, db_index=True)


@architect.install('partition', type='range', subtype='date', constraint='month', column='timestamp')
@foreign_init
class UserAccessLog(models.Model):
    TYPE_LOGIN = 'login'
    TYPE_LOGOUT = 'logout'
    TYPE_FAILURE = 'failure'

    ACTIONS = (
        (TYPE_LOGIN, 'Login'),
        (TYPE_LOGOUT, 'Logout'),
        (TYPE_FAILURE, 'Login Failure')
    )

    id = models.BigAutoField(primary_key=True)
    user_id = models.CharField(max_length=255, db_index=True)
    action = models.CharField(max_length=20, choices=ACTIONS)
    ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent_fk = models.ForeignKey(
        UserAgent, null=True, on_delete=models.PROTECT, db_column="user_agent_id")
    user_agent = ForeignValue(user_agent_fk, truncate=True)
    path = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(default=datetime.utcnow)

    def __str__(self):
        return f'{self.timestamp}: {self.user_id} - {self.action}'


class HQOauthApplication(models.Model):
    application = models.OneToOneField(
        APPLICATION_MODEL,
        on_delete=models.CASCADE,
        related_name='hq_application',
    )
    pkce_required = models.BooleanField(default=True)


def pkce_required(client_id):
    try:
        application = HQOauthApplication.objects.get(application__client_id=client_id)
        return application.pkce_required
    except HQOauthApplication.DoesNotExist:
        return False
