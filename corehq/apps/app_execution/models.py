from functools import cached_property

from django.contrib.auth.models import User
from django.db import models

from corehq.apps.app_execution import const
from corehq.apps.app_execution.api import FormplayerSession, LocalUserClient
from corehq.apps.app_execution.data_model import AppWorkflow
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.util.jsonattrs import AttrsObject


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
        return FormplayerSession(client, self.app_id, self.form_mode)
