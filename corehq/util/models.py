from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models
from collections import namedtuple


AwsMeta = namedtuple('AwsMeta', 'notification_type main_type sub_type '
                                'email reason headers timestamp '
                                'destination')


class NotificationType(object):
    BOUNCE = "Bounce"
    COMPLAINT = "Complaint"
    UNDETERMINED = "Undetermined"


class BounceType(object):
    PERMANENT = "Permanent"
    UNDETERMINED = "Undetermined"
    TRANSIENT = "Transient"  # todo handle these


class BounceSubType(object):
    """
    This is part of the information AWS SES uses to classify a bounce. Most
    crucial in limiting are the "Suppressed" emails, which have bounced on ANY
    AWS SES client's list within the past 14 days.
    """
    GENERAL = "General"
    SUPPRESSED = "Suppressed"
    UNDETERMINED = "Undetermined"
    CHOICES = (
        (GENERAL, GENERAL),
        (SUPPRESSED, SUPPRESSED),
        (UNDETERMINED, UNDETERMINED),
    )


class BouncedEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True, unique=True)


class TransientBounceEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    headers = JSONField(blank=True, null=True)


class PermanentBounceMeta(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    bounced_email = models.ForeignKey(BouncedEmail, on_delete=models.PROTECT)
    timestamp = models.DateTimeField()
    sub_type = models.CharField(
        max_length=20,
        choices=BounceSubType.CHOICES
    )
    headers = JSONField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    destination = ArrayField(models.EmailField(), default=list, blank=True, null=True)


class ComplaintBounceMeta(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    bounced_email = models.ForeignKey(BouncedEmail, on_delete=models.PROTECT)
    timestamp = models.DateTimeField()
    headers = JSONField(blank=True, null=True)
    feedback_type = models.CharField(max_length=50, blank=True, null=True)
    sub_type = models.CharField(max_length=50, blank=True, null=True)
    destination = ArrayField(models.EmailField(), default=list, blank=True, null=True)
