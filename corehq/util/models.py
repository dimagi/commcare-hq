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


# The number of General bounces we accept before rejecting an email hard
GENERAL_BOUNCE_THRESHOLD = 3


class BouncedEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True, unique=True)

    @staticmethod
    def get_hard_bounced_emails(list_of_emails):
        # these are any Bounced Email Records we have
        bounced_emails = set(
            BouncedEmail.objects.filter(email__in=list_of_emails).values_list(
                'email', flat=True)
        )

        # These are emails that were marked as Suppressed or Undetermined
        # by SNS metadata, meaining they definitely hard bounced
        bad_emails = set(
            PermanentBounceMeta.objects.filter(sub_type__in=[
                BounceSubType.UNDETERMINED, BounceSubType.SUPPRESSED
            ], bounced_email__email__in=bounced_emails).values_list(
                'bounced_email__email', flat=True)
        )

        # These are definite complaints against us
        complaints = set(
            ComplaintBounceMeta.objects.filter(
                bounced_email__email__in=bounced_emails.difference(bad_emails)
            ).values_list('bounced_email__email', flat=True)
        )
        bad_emails.update(complaints)

        for remaining_email in bounced_emails.difference(bad_emails):
            meta_query = PermanentBounceMeta.objects.filter(
                bounced_email__email=remaining_email)
            if not meta_query.exists():
                # check to see if this is Transiently bouncing
                transient_bounce_query = TransientBounceEmail.objects.filter(
                    email=remaining_email
                )
                if not transient_bounce_query.exists():
                    # There is no metadata at all for this email, so we assume
                    # a hard bounce
                    bad_emails.add(remaining_email)
            elif meta_query.count() > GENERAL_BOUNCE_THRESHOLD:
                # This email has too many general bounces recorded against it
                bad_emails.add(remaining_email)

        return bad_emails


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
