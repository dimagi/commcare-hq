from functools import cached_property

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import functions

from corehq.apps.app_execution import const
from corehq.apps.app_execution.api import FormplayerSession, LocalUserClient
from corehq.apps.app_execution.data_model import AppWorkflow
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.sql_db.functions import MakeInterval
from corehq.util.jsonattrs import AttrsObject


class AppWorkflowManager(models.Manager):
    def get_due(self):
        cutoff = functions.Now() - MakeInterval("mins", models.F("run_every"))
        return self.filter(last_run__isnull=True) | self.filter(
            last_run__lt=cutoff
        )


class AppWorkflowConfig(models.Model):
    FORM_MODE_CHOICES = [
        (const.FORM_MODE_HUMAN, "Human: Answer each question individually and submit form"),
        (const.FORM_MODE_NO_SUBMIT, "No Submit: Answer all questions but don't submit the form"),
        (const.FORM_MODE_IGNORE, "Ignore: Do not complete or submit forms"),
    ]
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=36)
    django_user = models.ForeignKey(User, on_delete=models.CASCADE)
    workflow = AttrsObject(AppWorkflow)
    form_mode = models.CharField(max_length=255, choices=FORM_MODE_CHOICES)
    sync_before_run = models.BooleanField(default=False, help_text="Sync user data before running")
    run_every = models.IntegerField(default=0, help_text="Number of minutes between runs")
    last_run = models.DateTimeField(null=True, blank=True)
    notification_emails = ArrayField(models.EmailField(), default=list, help_text="Emails to notify on failure")

    objects = AppWorkflowManager()

    class Meta:
        unique_together = ("domain", "user_id")

    @cached_property
    def app_name(self):
        app = get_brief_app(self.domain, self.app_id)
        return app.name

    def get_formplayer_session(self):
        client = LocalUserClient(
            domain=self.domain,
            username=self.django_user.username,
            user_id=self.user_id
        )
        return FormplayerSession(client, self.app_id, self.form_mode, self.sync_before_run)
