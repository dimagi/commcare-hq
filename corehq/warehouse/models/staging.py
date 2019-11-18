from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models
from django.db.models import Index

from corehq.form_processor.models import XFormInstanceSQL
from corehq.warehouse.models.dimensions import ApplicationDim, UserDim


class StagingTable(models.Model):
    batch = models.ForeignKey(
        'Batch',
        on_delete=models.PROTECT,
    )

    class Meta(object):
        abstract = True


class LocationStagingTable(StagingTable):
    """
    Represents the staging table to dump data before loading into the LocationDim

    Grain: location_id
    """
    domain = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    site_code = models.CharField(max_length=100)
    location_id = models.CharField(max_length=255)
    location_type_id = models.IntegerField()
    external_id = models.CharField(max_length=255, null=True)
    supply_point_id = models.CharField(max_length=255, null=True)
    user_id = models.CharField(max_length=255)

    sql_location_id = models.IntegerField()
    sql_parent_location_id = models.IntegerField(null=True)

    location_last_modified = models.DateTimeField(null=True)
    location_created_on = models.DateTimeField(null=True)

    is_archived = models.NullBooleanField()

    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)

    location_type_name = models.CharField(max_length=255)
    location_type_code = models.SlugField(db_index=False, null=True)

    location_type_last_modified = models.DateTimeField(null=True)


class GroupStagingTable(StagingTable):
    """
    Represents the staging table to dump data before loading into the GroupDim

    Grain: group_id
    """
    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=100)
    domain = models.CharField(max_length=100)
    user_ids = ArrayField(models.CharField(max_length=255), null=True)
    removed_user_ids = ArrayField(models.CharField(max_length=255), null=True)

    case_sharing = models.NullBooleanField()
    reporting = models.NullBooleanField()

    group_last_modified = models.DateTimeField(null=True)


class UserStagingTable(StagingTable):
    """
    Represents the staging table to dump data before loading into the UserDim

    Grain: user_id
    """
    user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=150)
    first_name = models.TextField(null=True)
    last_name = models.TextField(null=True)
    email = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)
    base_doc = models.CharField(max_length=100)
    domain = models.CharField(max_length=100, null=True, blank=True)

    assigned_location_ids = ArrayField(models.CharField(max_length=255), null=True)
    domain_memberships = JSONField(null=True)
    is_active = models.BooleanField()
    is_staff = models.BooleanField()
    is_superuser = models.BooleanField()

    last_login = models.DateTimeField(null=True)
    date_joined = models.DateTimeField()

    user_last_modified = models.DateTimeField(null=True)


class DomainStagingTable(StagingTable):
    """
    Represents the staging table to dump data before loading into the DomainDim

    Grain: domain_id
    """
    domain_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=100)
    default_timezone = models.CharField(max_length=255)
    hr_name = models.CharField(max_length=255, null=True)
    creating_user_id = models.CharField(max_length=255, null=True)
    project_type = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)

    is_active = models.BooleanField()
    case_sharing = models.BooleanField()
    commtrack_enabled = models.BooleanField()
    is_test = models.CharField(max_length=255)
    location_restriction_for_users = models.BooleanField()
    use_sql_backend = models.NullBooleanField()
    first_domain_for_user = models.NullBooleanField()

    domain_last_modified = models.DateTimeField(null=True)
    domain_created_on = models.DateTimeField(null=True)


class FormStagingTable(StagingTable):
    """
    Represents the staging table to dump data before loading into the FormFact

    Grain: form_id
    """
    form_id = models.CharField(max_length=255, unique=True)

    domain = models.CharField(max_length=255, default=None)
    app_id = models.CharField(max_length=255, null=True)
    xmlns = models.CharField(max_length=255, default=None)
    user_id = models.CharField(max_length=255, null=True)

    # The time at which the server has received the form
    received_on = models.DateTimeField()
    deleted_on = models.DateTimeField(null=True)
    edited_on = models.DateTimeField(null=True)

    time_end = models.DateTimeField(null=True, blank=True)
    time_start = models.DateTimeField(null=True, blank=True)
    commcare_version = models.CharField(max_length=8, blank=True, null=True)
    app_version = models.PositiveIntegerField(null=True, blank=True)

    build_id = models.CharField(max_length=255, null=True)

    state = models.PositiveSmallIntegerField(
        choices=XFormInstanceSQL.STATES,
        default=XFormInstanceSQL.NORMAL
    )

    class Meta:
        indexes = [
            Index(fields=['user_id']),
        ]


class SyncLogStagingTable(StagingTable):
    """
    Represents the staging table to dump data before loading into the SyncLogFact

    Grain: sync_log_id
    """
    sync_log_id = models.CharField(max_length=255)
    sync_date = models.DateTimeField(null=True)

    # this is only added as of 11/2016 - not guaranteed to be set
    domain = models.CharField(max_length=255, null=True)
    user_id = models.CharField(max_length=255, null=True)

    # this is only added as of 11/2016 and only works with app-aware sync
    build_id = models.CharField(max_length=255, null=True)

    duration = models.IntegerField(null=True)  # in seconds

    class Meta:
        indexes = [
            Index(fields=['user_id']),
        ]


class ApplicationStagingTable(StagingTable):
    """
    Represents the staging table to dump data before loading into the ApplicationDim

    Grain: application_id
    """
    application_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=100)
    application_last_modified = models.DateTimeField(null=True)
    doc_type = models.CharField(max_length=100)
    version = models.IntegerField(null=True)
    copy_of = models.CharField(max_length=255, null=True, blank=True)


class AppStatusFormStaging(StagingTable):
    domain = models.CharField(max_length=255, default=None, db_index=True)
    app_dim = models.ForeignKey(ApplicationDim, on_delete=models.PROTECT, null=True)
    user_dim = models.ForeignKey(UserDim, on_delete=models.PROTECT)
    last_submission = models.DateTimeField(db_index=True)
    submission_build_version = models.CharField(max_length=255, null=True, db_index=True)
    commcare_version = models.CharField(max_length=255, null=True, db_index=True)


class AppStatusSynclogStaging(StagingTable):
    last_sync = models.DateTimeField(null=True, db_index=True)
    domain = models.CharField(max_length=255, null=True, db_index=True)
    user_dim = models.ForeignKey(UserDim, on_delete=models.PROTECT)
