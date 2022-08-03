from corehq.apps.users.models import Invitation, InvitationStatus
from corehq.util.models import BounceType


def handle_email_invite_message(message, invite_id):
    try:
        invite = Invitation.objects.get(uuid=invite_id)
    except Invitation.DoesNotExist:
        return

    event_type = message.get('eventType')
    if event_type == 'Bounce':
        bounce_type = message.get('bounce', {}).get('bounceType')
        if bounce_type == BounceType.TRANSIENT:  # probably a vacation responder
            invite.email_status = InvitationStatus.DELIVERED
        else:
            invite.email_status = InvitationStatus.BOUNCED
    elif event_type == 'Send':
        invite.email_status = InvitationStatus.SENT
    elif event_type == 'Delivery':
        invite.email_status = InvitationStatus.DELIVERED

    invite.save()
