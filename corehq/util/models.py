import datetime

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


# The number of non supressed or undetermined bounces
# we accept before hard rejecting an email
BOUNCE_EVENT_THRESHOLD = 3

HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE = 24

# Prior to this date we do not have reliable SNS metadata for emails.
# In order to get rid of this, we'll want to slowly roll the date back and
# let the emails re-bounce while keeping an eye on the bounce rate. Once we're
# confident the rate is stable, continue rolling back until Jan 1st 2020 and then
# this date requirement can be removed. The slow rollback is to avoid having a sudden
# jump in email bounces from the initial bounces we had cut off in the beginning.
LEGACY_BOUNCE_MANAGER_DATE = datetime.datetime(2020, 2, 10)


class BouncedEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True, unique=True)

    @classmethod
    def is_email_over_limits(cls, email):
        """
        Determines if an email has passed bounce event limits for general
        and transient bounces
        :param email: string
        :return: boolean
        """
        transient_bounce_query = TransientBounceEmail.get_active_query().filter(
            email=email,
        )
        general_bounce_query = PermanentBounceMeta.objects.filter(
            bounced_email__email=email,
            sub_type=BounceSubType.GENERAL,
        )
        return (
            transient_bounce_query.count() + general_bounce_query.count() > BOUNCE_EVENT_THRESHOLD
        )

    @classmethod
    def get_hard_bounced_emails(cls, list_of_emails):
        # these are any Bounced Email Records we have
        bounced_emails = set(
            BouncedEmail.objects.filter(email__in=list_of_emails).values_list(
                'email', flat=True
            )
        )

        transient_emails = set(
            TransientBounceEmail.get_active_query().filter(
                email__in=list_of_emails,
            ).values_list(
                'email', flat=True
            )
        )
        bounced_emails.update(transient_emails)

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

        # see note surrounding LEGACY_BOUNCE_MANAGER_DATE above
        legacy_bounced_emails = set(
            BouncedEmail.objects.filter(
                email__in=list_of_emails,
                created__lte=LEGACY_BOUNCE_MANAGER_DATE,
            ).values_list(
                'email', flat=True
            )
        )
        bad_emails.update(legacy_bounced_emails)

        for remaining_email in bounced_emails.difference(bad_emails):
            if cls.is_email_over_limits(remaining_email):
                bad_emails.add(remaining_email)

        return bad_emails


class TransientBounceEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    headers = JSONField(blank=True, null=True)

    @classmethod
    def get_expired_query(cls):
        return cls.objects.filter(
            created__lt=datetime.datetime.utcnow() - datetime.timedelta(
                hours=HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE + 1
            )
        )

    @classmethod
    def delete_expired_bounces(cls):
        cls.get_expired_query().delete()

    @classmethod
    def get_active_query(cls):
        return cls.objects.filter(
            created__gte=datetime.datetime.utcnow() - datetime.timedelta(
                hours=HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE)
        )


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
