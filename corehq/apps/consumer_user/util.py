from datetime import timedelta

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.urls import reverse
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import ugettext as _

from corehq.apps.consumer_user.models import ConsumerUserInvitation


class InvitationError(Exception):
    def __init__(self, msg, status, *args):
        self.msg = msg
        self.status = status
        super().__init__(*args)


class InvitationRedirect(InvitationError):
    def __init__(self, redirect_to):
        self.redirect_to = redirect_to
        super().__init__('', 302)


def get_invitation_obj(invitation):
    try:
        decoded_invitation = urlsafe_base64_decode(TimestampSigner().unsign(invitation,
                                                                            max_age=timedelta(days=30)))
        invitation_obj = ConsumerUserInvitation.objects.get(id=decoded_invitation)
        if invitation_obj.accepted:
            url = reverse('consumer_user:consumer_user_login')
            raise InvitationRedirect(url)
        elif not invitation_obj.active:
            raise InvitationError(_("Invitation is inactive"), status=400)
        else:
            return invitation_obj
    except (BadSignature, ConsumerUserInvitation.DoesNotExist):
        raise InvitationError(_("Invalid invitation"), status=400)
    except SignatureExpired:
        raise InvitationError(_("Invitation is expired"), status=400)
