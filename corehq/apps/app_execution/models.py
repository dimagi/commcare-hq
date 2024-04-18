from django.contrib.auth.models import User
from django.db import models

from corehq.apps.app_execution.api import FormplayerSession, LocalUserClient
from corehq.apps.app_execution.data_model import AppWorkflow
from corehq.util.jsonattrs import AttrsObject


class AppWorkflowConfig(models.Model):
    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=36)
    django_user = models.ForeignKey(User, on_delete=models.CASCADE)
    workflow = AttrsObject(AppWorkflow)

    class Meta:
        unique_together = ("domain", "user_id")

    def get_formplayer_session(self):
        client = LocalUserClient(
            domain=self.domain,
            username=self.django_user.username,
            user_id=self.user_id
        )
        return FormplayerSession(client, self.app_id)
