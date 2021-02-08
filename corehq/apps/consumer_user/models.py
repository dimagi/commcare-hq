from django.contrib.auth.models import User
from django.db import models


class ConsumerUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)


class ConsumerUserCaseRelationship(models.Model):
    case_user = models.ForeignKey(ConsumerUser, on_delete=models.CASCADE)
    case_id = models.CharField(max_length=255)  # uuid for the `commcare-caseuser` case
    domain = models.CharField(max_length=255)


class ConsumerUserInvitation(models.Model):
    email = models.EmailField()  # the email address the invite was sent to
    case_id = models.CharField(max_length=255)  # uuid for the `commcare-caseuser` case
    domain = models.CharField(max_length=255)
    accepted = models.BooleanField(default=False)
    invited_by = models.CharField(max_length=255)  # UUID of the (Web|Commcare) User who created this invitation
    invited_on = models.DateTimeField()  # datetime when this invitation was created.
    active = models.BooleanField(default=True)
