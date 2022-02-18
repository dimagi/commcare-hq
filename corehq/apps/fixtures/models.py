from datetime import datetime

from django.db import models

from .couchmodels import (  # noqa: F401
    _id_from_doc,
    FIXTURE_BUCKET,
    FieldList,
    FixtureDataItem,
    FixtureDataType,
    FixtureItemField,
    FixtureOwnership,
    FixtureTypeField,
)


class UserFixtureType:
    LOCATION = 1
    CHOICES = (
        (LOCATION, "Location"),
    )


class UserFixtureStatus(models.Model):
    """Keeps track of when a user needs to re-sync a fixture"""
    user_id = models.CharField(max_length=100, db_index=True)
    fixture_type = models.PositiveSmallIntegerField(choices=UserFixtureType.CHOICES)
    last_modified = models.DateTimeField()

    DEFAULT_LAST_MODIFIED = datetime.min

    class Meta:
        app_label = 'fixtures'
        unique_together = ("user_id", "fixture_type")
