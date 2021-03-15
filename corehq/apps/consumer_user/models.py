from django.contrib.auth.models import User
from django.core.signing import TimestampSigner
from django.db import models
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from corehq.util.models import GetOrNoneManager


class ConsumerUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    objects = GetOrNoneManager()


class ConsumerUserCaseRelationship(models.Model):
    consumer_user = models.ForeignKey(ConsumerUser, on_delete=models.CASCADE)
    case_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    class Meta:
        unique_together = (
            'case_id',
            'domain',
        )


class ConsumerUserInvitation(models.Model):
    email = models.EmailField()
    case_id = models.CharField(max_length=255)
    demographic_case_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    accepted = models.BooleanField(default=False)
    invited_by = models.CharField(max_length=255)
    invited_on = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    def make_inactive(self):
        self.active = False
        self.save(update_fields=['active'])

    def accept(self):
        self.accepted = True
        self.save(update_fields=['accepted'])

    @classmethod
    def create_invitation(cls, case_id, domain, demographic_case_id, opened_by, email):
        instance = cls(
            case_id=case_id,
            domain=domain,
            demographic_case_id=demographic_case_id,
            invited_by=opened_by,
            email=email
        )
        instance.save()
        return instance

    def signature(self):
        """Creates an encrypted key that can be used in a URL to accept this invitation
        """
        return TimestampSigner().sign(urlsafe_base64_encode(force_bytes(self.pk)))
