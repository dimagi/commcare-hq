from collections import defaultdict

from corehq.toggles import BLOCKED_EMAIL_DOMAIN_RECIPIENTS
from corehq.util.email_event_utils import get_emails_to_never_bounce
from corehq.util.models import (
    LEGACY_BOUNCE_MANAGER_DATE,
    BouncedEmail,
    BounceSubType,
    ComplaintBounceMeta,
    PermanentBounceMeta,
    TransientBounceEmail,
)


def _get_blocked_emails(emails):
    return [email for email in emails if BLOCKED_EMAIL_DOMAIN_RECIPIENTS.enabled(email)]


def _get_badly_formatted_emails(emails):
    return [email for email in emails if BouncedEmail.is_bad_email_format(email)]


def _get_bounced_emails(emails):
    bounced_emails = set(BouncedEmail.objects.filter(email__in=emails).values_list('email', flat=True))
    transient_emails = set(
        TransientBounceEmail.get_active_query()
        .filter(
            email__in=emails,
        )
        .values_list('email', flat=True)
    )
    bounced_emails.update(transient_emails)
    return bounced_emails


def _get_permanently_bounced_emails(bounced_emails):
    """
    For the given emails, find any records of these emails being bounced
    and if so, check if they are permanently bounced.
    TODO: can we just check if there are any Permanent Bounces for the given emails?
    """

    # These are emails that were marked as Suppressed or Undetermined
    # by SNS metadata, meaning they definitely hard bounced
    permanent_bounces = set(
        PermanentBounceMeta.objects.filter(
            sub_type__in=[BounceSubType.UNDETERMINED, BounceSubType.SUPPRESSED],
            bounced_email__email__in=bounced_emails,
        ).values_list('bounced_email__email', flat=True)
    )
    return permanent_bounces


def _get_complaint_bounced_emails(emails):
    # These are definite complaints against us
    return set(
        ComplaintBounceMeta.objects.filter(bounced_email__email__in=emails).values_list(
            'bounced_email__email', flat=True
        )
    )


def _get_legacy_bounced_emails(emails):
    # see note surrounding LEGACY_BOUNCE_MANAGER_DATE above
    return set(
        BouncedEmail.objects.filter(
            email__in=emails,
            created__lte=LEGACY_BOUNCE_MANAGER_DATE,
        ).values_list('email', flat=True)
    )


def _get_emails_over_limit(bounced_emails):
    return [email for email in bounced_emails if BouncedEmail.is_email_over_limits(email)]


def get_email_statuses(emails):
    statuses_by_email = defaultdict(dict)

    blocked_emails = _get_blocked_emails(emails)
    badly_formatted_emails = _get_badly_formatted_emails(emails)
    bounced_emails = _get_bounced_emails(emails)
    permanently_bounced_emails = _get_permanently_bounced_emails(bounced_emails)
    complaint_bounced_emails = _get_complaint_bounced_emails(bounced_emails)
    legacy_bounced_emails = _get_legacy_bounced_emails(emails)
    emails_over_limit = _get_emails_over_limit(emails)
    whitelisted_emails = set(get_emails_to_never_bounce()).union(set(emails))
    for email in emails:
        statuses_for_email = {
            'blocked': email in blocked_emails,
            'invalid_format': email in badly_formatted_emails,
            'permanently_bounced': email in permanently_bounced_emails,
            'complaint_bounced': email in complaint_bounced_emails,
            'legacy_bounced': email in legacy_bounced_emails,
            'over_limits': email in emails_over_limit,
            'whitelisted': email in whitelisted_emails,
        }
        statuses_by_email[email] = statuses_for_email
    return statuses_by_email
