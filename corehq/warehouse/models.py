from django.db import models
from django_fsm import FSMField, transition

from .states import (
    FACT_TABLE_NEEDS_UPDATING,
    FACT_TABLE_BATCH_DUMPED,
    FACT_TABLE_READY,
    FACT_TABLE_FAILED,
    FACT_TABLE_DECOMMISSIONED,
)


class FactTableState(models.Model):
    domain = models.CharField(max_length=255)
    report_slug = models.CharField(max_length=255)
    state = FSMField(default=FACT_TABLE_NEEDS_UPDATING)
    last_modified = models.DateTimeField(auto_now=True)
    last_batch_id = models.CharField(max_length=255)

    class Meta(object):
        index_together = ('domain', 'state')

    @transition(
        field=state,
        source=[FACT_TABLE_NEEDS_UPDATING, FACT_TABLE_FAILED],
        target=FACT_TABLE_BATCH_DUMPED,
        on_error=FACT_TABLE_FAILED,
    )
    def dump_to_intermediate_table(self):
        return

    @transition(
        field=state,
        source=FACT_TABLE_BATCH_DUMPED,
        target=FACT_TABLE_READY,
        on_error=FACT_TABLE_FAILED,
    )
    def process_intermediate_table(self):
        return

    @transition(
        field=state,
        source=FACT_TABLE_READY,
        target=FACT_TABLE_NEEDS_UPDATING,
        on_error=FACT_TABLE_FAILED
    )
    def queue(self):
        return

    @transition(
        field=state,
        source='*',
        target=FACT_TABLE_FAILED,
    )
    def fail(self):
        return

    @transition(
        field=state,
        source='*',
        target=FACT_TABLE_DECOMMISSIONED,
    )
    def decommission(self):
        return


class BaseDim(models.Model):
    domain = models.CharField(max_length=255)

    dim_last_modified = models.DateTimeField(auto_now=True)
    dim_created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UserDim(BaseDim):
    user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    user_type = models.CharField(max_length=255)

    is_active = models.BooleanField()
    is_staff = models.BooleanField()
    is_superuser = models.BooleanField()

    last_login = models.DateTimeField()
    date_joined = models.DateTimeField()


class GroupDim(BaseDim):
    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    case_sharing = models.BooleanField()
    reporting = models.BooleanField()

    group_last_modified = models.DateTimeField()


class LocationDim(BaseDim):
    location_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    site_code = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255)
    supply_point_id = models.CharField(max_length=255, null=True)

    location_type_id = models.CharField(max_length=255)
    location_type_name = models.CharField(max_length=255)
    location_type_code = models.CharField(max_length=255)

    is_archived = models.BooleanField()

    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)

    location_last_modified = models.DateTimeField()
    location_created_on = models.DateTimeField()


class DomainDim(BaseDim):
    domain_id = models.CharField(max_length=255)
    default_timezone = models.CharField(max_length=255)
    hr_name = models.CharField(max_length=255)
    creating_user_id = models.CharField(max_length=255)
    project_type = models.CharField(max_length=255)

    is_active = models.BooleanField()
    case_sharing = models.BooleanField()
    commtrack_enabled = models.BooleanField()
    is_test = models.BooleanField()
    location_restriction_for_users = models.BooleanField()
    use_sql_backend = models.BooleanField()
    first_domain_for_user = models.BooleanField()

    domain_last_modified = models.DateTimeField()
    domain_created_on = models.DateTimeField()


class UserLocationDim(BaseDim):
    location_id = models.CharField(max_length=100)
    user_id = models.CharField(max_length=255)


class UserGroupDim(BaseDim):
    group_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)
