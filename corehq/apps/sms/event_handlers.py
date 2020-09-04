from corehq.apps.sms.models import MessagingSubEvent, MessagingEvent


def handle_email_messaging_subevent(message, subevent_id):
    try:
        subevent = MessagingSubEvent.objects.get(id=subevent_id)
    except MessagingSubEvent.DoesNotExist:
        return

    event_type = message.get('eventType')
    if event_type == 'Bounce':
        additional_error_text = ''

        bounce_type = message.get('bounce', {}).get('bounceType')
        if bounce_type:
            additional_error_text = f"{bounce_type}."
        bounced_recipients = message.get('bounce', {}).get('bouncedRecipients',
                                                           [])
        recipient_addresses = []
        for bounced_recipient in bounced_recipients:
            recipient_addresses.append(bounced_recipient.get('emailAddress'))
        if recipient_addresses:
            additional_error_text = f"{additional_error_text} - {', '.join(recipient_addresses)}"

        subevent.error(MessagingEvent.ERROR_EMAIL_BOUNCED,
                       additional_error_text=additional_error_text)
    elif event_type == 'Send':
        subevent.status = MessagingEvent.STATUS_EMAIL_SENT
    elif event_type == 'Delivery':
        subevent.status = MessagingEvent.STATUS_EMAIL_DELIVERED
        subevent.additional_error_text = message.get('delivery', {}).get(
            'timestamp')

    subevent.save()
