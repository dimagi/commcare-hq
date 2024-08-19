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
from django.utils.translation import gettext_lazy


class AppWorkflowManager(models.Manager):
    def get_due(self):
        cutoff = functions.Now() - MakeInterval("mins", models.F("run_every"))
        return self.filter(run_every__isnull=False, last_run__isnull=True) | self.filter(
            last_run__lt=cutoff
        )


class AppWorkflowConfig(models.Model):
    FORM_MODE_CHOICES = [
        (const.FORM_MODE_HUMAN, gettext_lazy("Human: Answer each question individually and submit form")),
        (const.FORM_MODE_NO_SUBMIT, gettext_lazy("No Submit: Answer all questions but don't submit the form")),
        (const.FORM_MODE_IGNORE, gettext_lazy("Ignore: Do not complete or submit forms")),
    ]
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=36)
    django_user = models.ForeignKey(User, on_delete=models.CASCADE)
    workflow = AttrsObject(AppWorkflow)
    form_mode = models.CharField(max_length=255, choices=FORM_MODE_CHOICES)
    sync_before_run = models.BooleanField(default=False, help_text=gettext_lazy("Sync user data before running"))
    run_every = models.IntegerField(
        help_text=gettext_lazy("Number of minutes between runs"), null=True, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    notification_emails = ArrayField(
        models.EmailField(), default=list, help_text=gettext_lazy("Emails to notify on failure"), blank=True
    )

    objects = AppWorkflowManager()

    @cached_property
    def app_name(self):
        app = get_brief_app(self.domain, self.app_id)
        return app.name

    @property
    def workflow_json(self):
        return AppWorkflowConfig.workflow_object_to_json_string(self.workflow)

    @staticmethod
    def workflow_object_to_json_string(workflow):
        return AppWorkflowConfig._meta.get_field("workflow").formfield().prepare_value(workflow)

    def get_formplayer_session(self):
        client = LocalUserClient(
            domain=self.domain,
            username=self.django_user.username,
            user_id=self.user_id
        )
        return FormplayerSession(client, self.app_id, self.form_mode, self.sync_before_run)


class AppExecutionLog(models.Model):
    workflow = models.ForeignKey(AppWorkflowConfig, on_delete=models.CASCADE)
    started = models.DateTimeField(auto_now_add=True)
    completed = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    output = models.TextField(blank=True)
    error = models.TextField(blank=True)

    @property
    def duration(self):
        if self.completed:
            return self.completed - self.started

    def __str__(self):
        return f"{self.workflow.name} - {self.started}"
