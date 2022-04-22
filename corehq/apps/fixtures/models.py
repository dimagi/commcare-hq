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


class UserLookupTableType:
    LOCATION = 1
    CHOICES = (
        (LOCATION, "Location"),
    )


class UserLookupTableStatus(models.Model):
    """Keeps track of when a user needs to re-sync a fixture"""
    user_id = models.CharField(max_length=100, db_index=True)
    fixture_type = models.PositiveSmallIntegerField(choices=UserLookupTableType.CHOICES)
    last_modified = models.DateTimeField()

    DEFAULT_LAST_MODIFIED = datetime.min

    class Meta:
        app_label = 'fixtures'
        db_table = 'fixtures_userfixturestatus'
        unique_together = ("user_id", "fixture_type")
