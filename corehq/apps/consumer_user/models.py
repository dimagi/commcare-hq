from datetime import timedelta

from django.contrib.auth.models import User
from django.core.signing import TimestampSigner
from django.db import models
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from corehq.apps.consumer_user.const import (
    CONSUMER_INVITATION_ACCEPTED,
    CONSUMER_INVITATION_ERROR,
    CONSUMER_INVITATION_STATUS,
)
from corehq.apps.hqcase.utils import update_case


class ConsumerUser(models.Model):
    """A user model that defines an individual patient, beneficiary, or consumer,
    and allows this person to log in to a subset of HQ.

    When authenticated, this user will have access to their data collected
    about them by FLWs.

    A ConsumerUser is not bound by a domain, and can access data collected
    about them across the platform

    This is linked with the regular Django User, as we use Django's auth to
    limit access.

    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)


class ConsumerUserCaseRelationship(models.Model):
    """An authorization model which links a ConsumerUser with a particular case
    that they should have access to. A ConsumerUser can have many
    ConsumerUserCaseRelationships.

    ConsumerUsers can have access to the cases listed in this table, and any
    subcases of that case.

    """
    consumer_user = models.ForeignKey(
        ConsumerUser,
        on_delete=models.CASCADE,
        related_name='case_relationships',
    )
    case_id = models.CharField(max_length=255, unique=True)
    domain = models.CharField(max_length=255)


class ConsumerUserInvitation(models.Model):
    """This model keeps track of the invitation status linked to a particular demographic case.

    The invitation workflow is triggered when a case of type
    CONSUMER_INVITATION_CASE_TYPE is created in the system. This case is
    written back to as the stages of the invitation are carried out so an app
    user can see what is happening, and can retrigger or change an invitation
    if need be.

    The invitation stores an email address - where the invite is sent, and the
    demographic_case_id, which defines which case the user will have access to
    once they accept the invite.

    Once a ConsumerUserInvitation is accepted by a consumer, a new
    ConsumerUserCaseRelationShip is created with the case_id set to the
    invitation's demographic_case_id.

    """
    email = models.EmailField()
    # The case id of the CONSUMER_INVITATION_CASE_TYPE which triggered this
    # invitation to be sent
    case_id = models.CharField(max_length=255)
    # The case id of the highest ancestor case the user will have access to
    # once they accept this invitation. This is normally a "demographic case",
    # or the case which corresponds to the person.
    demographic_case_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    accepted = models.BooleanField(default=False)
    invited_by = models.CharField(max_length=255)
    invited_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # There can be only one unaccepted invitation per demographic case
            models.UniqueConstraint(
                fields=['demographic_case_id'],
                condition=models.Q(accepted=False, active=True),
                name="multiple_open_invites",
            )
        ]

    def make_inactive(self):
        self.active = False
        self.save(update_fields=['active'])

    def accept_for_consumer_user(self, consumer_user):
        self.accepted = True
        self.save(update_fields=['accepted'])

        ConsumerUserCaseRelationship.objects.create(
            case_id=self.demographic_case_id,
            domain=self.domain,
            consumer_user=consumer_user
        )
        update_case(
            self.domain,
            self.case_id,
            {
                CONSUMER_INVITATION_STATUS: CONSUMER_INVITATION_ACCEPTED,
                CONSUMER_INVITATION_ERROR: "",
            }
        )

    def signature(self):
        """Creates an encrypted key that can be used in a URL to accept this invitation
        """
        return TimestampSigner().sign(urlsafe_base64_encode(force_bytes(self.pk)))

    @classmethod
    def from_signed_id(cls, signed_invitation_id):
        invitation_id = urlsafe_base64_decode(
            TimestampSigner().unsign(signed_invitation_id, max_age=timedelta(days=30))
        )
        return cls.objects.get(pk=invitation_id)
