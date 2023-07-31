import logging

from django.conf import settings
from django.utils.dateparse import parse_datetime

from corehq.util.metrics import metrics_counter
from corehq.util.models import (
    NotificationType,
    AwsMeta,
    BounceType,
    BouncedEmail,
    PermanentBounceMeta,
    ComplaintBounceMeta,
    TransientBounceEmail,
)


def log_email_sns_event(message):
    log_event = {
        'eventType': message.get('eventType'),
        'eventTimestamp': message.get('mail', {}).get('timestamp'),
        'commonHeaders': message.get('mail', {}).get('commonHeaders')
    }
    for key in ['bounce', 'complaint', 'delivery', 'reject', 'failure', 'deliveryDelay']:
        if key in message:
            log_event[key] = message.get(key)
    logging.info(log_event)


def handle_email_sns_event(message):
    """
    This expects message to be the "Message" portion of an AWS SNS Notification as
    sent by Amazon SNS, as described here:
    https://docs.aws.amazon.com/ses/latest/DeveloperGuide/event-publishing-retrieving-sns-examples.html
    :param message:
    :return:
    """
    for aws_meta in get_relevant_aws_meta(message):
        if aws_meta.notification_type == NotificationType.BOUNCE:
            if aws_meta.main_type == BounceType.PERMANENT:
                record_permanent_bounce(aws_meta)
                metrics_counter('commcare.email_sns_event.permanent_bounce_recorded')
            elif aws_meta.main_type == BounceType.TRANSIENT:
                record_transient_bounce(aws_meta)
                metrics_counter('commcare.email_sns_event.transient_bounce_recorded')
            elif aws_meta.main_type == BounceType.UNDETERMINED:
                record_permanent_bounce(aws_meta)
                metrics_counter('commcare.email_sns_event.undetermined_bounce_received')
        elif aws_meta.notification_type == NotificationType.COMPLAINT:
            record_complaint(aws_meta)
            metrics_counter('commcare.email_sns_event.complaint_recorded')
    log_email_sns_event(message)


def record_permanent_bounce(aws_meta):
    bounced_email, _ = BouncedEmail.objects.update_or_create(
        email=aws_meta.email,
    )
    exists = PermanentBounceMeta.objects.filter(
        bounced_email=bounced_email,
        timestamp=aws_meta.timestamp,
        sub_type=aws_meta.sub_type,
    ).exists()
    if not exists:
        PermanentBounceMeta.objects.create(
            bounced_email=bounced_email,
            timestamp=aws_meta.timestamp,
            sub_type=aws_meta.sub_type,
            headers=aws_meta.headers,
            reason=aws_meta.reason,
            destination=aws_meta.destination,
        )


def record_complaint(aws_meta):
    bounced_email, _ = BouncedEmail.objects.update_or_create(
        email=aws_meta.email,
    )
    exists = ComplaintBounceMeta.objects.filter(
        bounced_email=bounced_email,
        timestamp=aws_meta.timestamp,
    ).exists()
    if not exists:
        ComplaintBounceMeta.objects.create(
            bounced_email=bounced_email,
            timestamp=aws_meta.timestamp,
            headers=aws_meta.headers,
            feedback_type=aws_meta.main_type,
            sub_type=aws_meta.sub_type,
            destination=aws_meta.destination,
        )


def record_transient_bounce(aws_meta):
    exists = TransientBounceEmail.objects.filter(
        email=aws_meta.email,
        timestamp=aws_meta.timestamp,
    ).exists()
    if not exists:
        TransientBounceEmail.objects.create(
            email=aws_meta.email,
            timestamp=aws_meta.timestamp,
            headers=aws_meta.headers,
        )


def get_relevant_aws_meta(message_info):
    """
    Creates a list of AwsMeta objects from the Message portion of an AWS
    SNS Notification message.  One per recipient.
    :param message_info: (dict) the "Message" portion of an SNS notification
    :return: (list) AwsMeta objects
    """
    aws_info = []
    mail_info = message_info.get('mail', {})
    notification_type = message_info.get('notificationType') or message_info.get('eventType')
    if notification_type == NotificationType.BOUNCE:
        bounce_info = message_info['bounce']
        for recipient in bounce_info['bouncedRecipients']:
            aws_info.append(AwsMeta(
                notification_type=notification_type,
                main_type=bounce_info['bounceType'],
                sub_type=bounce_info['bounceSubType'],
                timestamp=parse_datetime(bounce_info['timestamp']),
                email=recipient['emailAddress'],
                reason=recipient.get('diagnosticCode'),
                headers=mail_info.get('commonHeaders', {}),
                destination=mail_info.get('destination', []),
            ))
    elif notification_type == NotificationType.COMPLAINT:
        complaint_info = message_info['complaint']
        for recipient in complaint_info['complainedRecipients']:
            aws_info.append(AwsMeta(
                notification_type=notification_type,
                main_type=message_info.get('complaintFeedbackType'),
                sub_type=complaint_info.get('complaintSubType'),
                timestamp=parse_datetime(complaint_info['timestamp']),
                email=recipient['emailAddress'],
                reason=None,
                headers=mail_info.get('commonHeaders', {}),
                destination=mail_info.get('destination', []),
            ))
    return aws_info


def get_emails_to_never_bounce():
    system_emails = [
        settings.SERVER_EMAIL,
        settings.DEFAULT_FROM_EMAIL,
        settings.SUPPORT_EMAIL,
        settings.PROBONO_SUPPORT_EMAIL,
        settings.ACCOUNTS_EMAIL,
        settings.DATA_EMAIL,
        settings.SUBSCRIPTION_CHANGE_EMAIL,
        settings.INTERNAL_SUBSCRIPTION_CHANGE_EMAIL,
        settings.BILLING_EMAIL,
        settings.INVOICING_CONTACT_EMAIL,
        settings.GROWTH_EMAIL,
        settings.MASTER_LIST_EMAIL,
        settings.SALES_EMAIL,
        settings.EULA_CHANGE_EMAIL,
        settings.PRIVACY_EMAIL,
        settings.CONTACT_EMAIL,
        settings.FEEDBACK_EMAIL,
        settings.SOFT_ASSERT_EMAIL,
        settings.DAILY_DEPLOY_EMAIL,
        settings.SAAS_OPS_EMAIL,
        settings.SAAS_REPORTING_EMAIL,
    ]
    system_emails.extend(settings.BOOKKEEPER_CONTACT_EMAILS)
    return [email for email in system_emails if isinstance(email, str)]


def get_bounced_system_emails():
    system_emails = get_emails_to_never_bounce()
    general_bounces = (
        BouncedEmail.objects
        .filter(email__in=system_emails)
        .values_list('email', flat=True)
    )
    transient_bounces = (
        TransientBounceEmail.objects
        .filter(email__in=system_emails)
        .values_list('email', flat=True)
    )
    return list(general_bounces) + list(transient_bounces)
