from django.contrib.auth.models import User
from django.db import models


class GetOrNoneManager(models.Manager):
    """
    Adds get_or_none method to objects
    """

    def get_or_none(self, **kwargs):
        try:
            return self.get(**kwargs)
        except self.model.DoesNotExist:
            return None


class ConsumerUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    objects = GetOrNoneManager()


class ConsumerUserCaseRelationship(models.Model):
    consumer_user = models.ForeignKey(ConsumerUser, on_delete=models.CASCADE)
    case_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    class Meta:
        unique_together = ('case_id', 'domain',)


class ConsumerUserInvitation(models.Model):
    email = models.EmailField()
    case_id = models.CharField(max_length=255)
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
    def create_invitation(cls, case_id, domain, opened_by, email):
        instance = cls(case_id=case_id,
                       domain=domain,
                       invited_by=opened_by,
                       email=email)
        instance.save()
        return instance
