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
    SNS Notification message.
    :param message_info: (dict) the "Message" portion of an SNS notification
    :return: (list) AwsMeta objects
    """
    aws_info = []
    mail_info = message_info.get('mail', {})
    if message_info['notificationType'] == NotificationType.BOUNCE:
        bounce_info = message_info['bounce']
        for recipient in bounce_info['bouncedRecipients']:
            aws_info.append(AwsMeta(
                notification_type=message_info['notificationType'],
                main_type=bounce_info['bounceType'],
                sub_type=bounce_info['bounceSubType'],
                timestamp=parse_datetime(bounce_info['timestamp']),
                email=recipient['emailAddress'],
                reason=recipient.get('diagnosticCode'),
                headers=mail_info.get('commonHeaders', {}),
                destination=mail_info.get('destination', []),
            ))
    elif message_info['notificationType'] == NotificationType.COMPLAINT:
        complaint_info = message_info['complaint']
        for recipient in complaint_info['complainedRecipients']:
            aws_info.append(AwsMeta(
                notification_type=message_info['notificationType'],
                main_type=message_info.get('complaintFeedbackType'),
                sub_type=complaint_info.get('complaintSubType'),
                timestamp=parse_datetime(complaint_info['timestamp']),
                email=recipient['emailAddress'],
                reason=None,
                headers=mail_info.get('commonHeaders', {}),
                destination=mail_info.get('destination', []),
            ))
    return aws_info
