from django.db import models


class IssuerId(models.Model):
    """
    This model is used to ensure unique, incrementing issuer IDs for users,
    and to look up a user given an issuer ID.
    obj.pk represents the serial issuer ID, later representations will be added as fields
    """
    domain = models.CharField(max_length=255, db_index=True)
    user_id = models.CharField(max_length=50, db_index=True, unique=True)
