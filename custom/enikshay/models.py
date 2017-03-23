from django.db import models


class IssuerId(models.Model):
    """
    This model is used to ensure unique, incrementing issuer IDs for users,
    and to look up a user given an issuer ID.
    obj.pk represents the serial issuer ID, later representations will be added as fields
    """
    domain = models.CharField(max_length=255, db_index=True)
    user_id = models.CharField(max_length=50, db_index=True, unique=True)


def set_issuer_id(domain, user):
    """Add a serially increasing custom user data "Issuer ID" to the user."""
    issuer_id, created = IssuerId.objects.get_or_create(domain=domain, user_id=user._id)
    user.user_data['issuer_id'] = issuer_id.pk
    user.save()
