from django.contrib.auth.models import User
from django.db import models


class ConsumerUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)


class ConsumerUserCaseRelationship(models.Model):
    consumer_user = models.ForeignKey(ConsumerUser, on_delete=models.CASCADE)
    case_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    class Meta:
        unique_together = ('case_id', 'domain',)


class ConsumerUserInvitation(models.Model):
    email = models.EmailField()
    case_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    accepted = models.BooleanField(default=False)
    invited_by = models.CharField(max_length=255)
    invited_on = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)
