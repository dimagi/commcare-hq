from django.db import models, transaction, connections

from corehq.warehouse.const import (
    USER_DIM_SLUG,
    GROUP_DIM_SLUG,
    LOCATION_DIM_SLUG,
    DOMAIN_DIM_SLUG,
    USER_LOCATION_DIM_SLUG,
    USER_GROUP_DIM_SLUG,
    USER_STAGING_SLUG,
    GROUP_STAGING_SLUG,
    DOMAIN_STAGING_SLUG,
)

from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.models.shared import WarehouseTable


class BaseDim(models.Model, WarehouseTable):
    domain = models.CharField(max_length=255)

    dim_last_modified = models.DateTimeField(auto_now=True)
    dim_created_on = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)

    @classmethod
    def commit(cls, start_datetime, end_datetime):
        with transaction.atomic(using=db_for_read_write(cls)):
            cls.load(start_datetime, end_datetime)

    class Meta:
        abstract = True

    @classmethod
    @unit_testing_only
    def clear_records(cls):
        database = db_for_read_write(cls)
        with connections[database].cursor() as cursor:
            cursor.execute("TRUNCATE {}".format(cls._meta.db_table))


class UserDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for Users

    Grain: user_id
    '''
    slug = USER_DIM_SLUG

    user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=150)
    user_type = models.CharField(max_length=100)
    first_name = models.CharField(max_length=30, null=True)
    last_name = models.CharField(max_length=30, null=True)
    email = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)

    is_active = models.BooleanField()
    is_staff = models.BooleanField()
    is_superuser = models.BooleanField()

    last_login = models.DateTimeField(null=True)
    date_joined = models.DateTimeField()

    @classmethod
    def dependencies(cls):
        return [USER_STAGING_SLUG]


class GroupDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for Groups

    Grain: group_id
    '''
    slug = GROUP_DIM_SLUG

    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    case_sharing = models.BooleanField()
    reporting = models.BooleanField()

    group_last_modified = models.DateTimeField()

    @classmethod
    def dependencies(cls):
        return [GROUP_STAGING_SLUG]


class LocationDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for Locations

    Grain: location_id
    '''
    slug = LOCATION_DIM_SLUG

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

    @classmethod
    def dependencies(cls):
        return []


class DomainDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for Domain

    Grain: domain_id
    '''
    slug = DOMAIN_DIM_SLUG

    domain_id = models.CharField(max_length=255)
    default_timezone = models.CharField(max_length=255)
    hr_name = models.CharField(max_length=255, null=True)
    creating_user_id = models.CharField(max_length=255, null=True)
    project_type = models.CharField(max_length=255, null=True)

    is_active = models.BooleanField()
    case_sharing = models.BooleanField()
    commtrack_enabled = models.BooleanField()
    is_test = models.BooleanField()
    location_restriction_for_users = models.BooleanField()
    use_sql_backend = models.BooleanField()
    first_domain_for_user = models.BooleanField()

    domain_last_modified = models.DateTimeField(null=True)
    domain_created_on = models.DateTimeField(null=True)

    @classmethod
    def dependencies(cls):
        return [DOMAIN_STAGING_SLUG]


class UserLocationDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for User and Location mapping

    Grain: user_id, location_id
    '''
    slug = USER_LOCATION_DIM_SLUG

    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    location_dim = models.ForeignKey('LocationDim', on_delete=models.CASCADE)

    @classmethod
    def dependencies(cls):
        return [USER_DIM_SLUG, LOCATION_DIM_SLUG]


class UserGroupDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for User and Group mapping

    Grain: user_id, group_id
    '''
    slug = USER_GROUP_DIM_SLUG

    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    group_dim = models.ForeignKey('GroupDim', on_delete=models.CASCADE)

    @classmethod
    def dependencies(cls):
        return [USER_DIM_SLUG, GROUP_DIM_SLUG]
