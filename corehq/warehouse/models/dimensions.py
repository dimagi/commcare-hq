from __future__ import absolute_import
from django.db import models, transaction

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
    LOCATION_STAGING_SLUG,
    APPLICATION_DIM_SLUG,
    APPLICATION_STAGING_SLUG,
    DOMAIN_MEMBERSHIP_DIM_SLUG,
)

from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import unit_testing_only
from corehq.warehouse.etl import CustomSQLETLMixin
from corehq.warehouse.models.shared import WarehouseTable
from corehq.warehouse.utils import truncate_records_for_cls


class BaseDim(models.Model, WarehouseTable):
    batch = models.ForeignKey(
        'Batch',
        on_delete=models.PROTECT,
    )

    dim_last_modified = models.DateTimeField(auto_now=True)
    dim_created_on = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField()

    @classmethod
    def commit(cls, batch):
        with transaction.atomic(using=db_for_read_write(cls)):
            cls.load(batch)
        return True

    class Meta(object):
        abstract = True

    @classmethod
    @unit_testing_only
    def clear_records(cls):
        truncate_records_for_cls(cls, cascade=True)


class UserDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for Users

    Grain: user_id
    '''
    slug = USER_DIM_SLUG

    user_id = models.CharField(max_length=255, unique=True)
    username = models.CharField(max_length=150)
    user_type = models.CharField(max_length=100)
    first_name = models.CharField(max_length=30, null=True)
    last_name = models.CharField(max_length=30, null=True)
    email = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)

    is_active = models.NullBooleanField()
    is_staff = models.NullBooleanField()
    is_superuser = models.NullBooleanField()

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

    group_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    case_sharing = models.NullBooleanField()
    reporting = models.NullBooleanField()

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

    domain = models.CharField(max_length=255)
    location_id = models.CharField(max_length=100, unique=True)
    sql_location_id = models.IntegerField()
    name = models.CharField(max_length=255)
    site_code = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, null=True)
    supply_point_id = models.CharField(max_length=255, null=True)
    level = models.IntegerField(null=True)

    location_type_id = models.IntegerField()
    location_type_name = models.CharField(max_length=255)
    location_type_code = models.CharField(max_length=255)

    # List of location levels flattened out. If a location is at level 3
    # then this should have levels 0, 1, 2, 3 populated. Each level contains
    # the sql id of the location. The lowest level location is always 0 and the
    # root location is always the highest location level 3.
    #
    # In an example of Canada -> Quebec -> Montreal and we are looking at the Montreal location:
    #
    # location_level_0 = Montreal.sql_location_id
    # location_level_1 = Quebec.sql_location_id
    # location_level_2 = Canada.sql_location_id
    location_level_0 = models.IntegerField(db_index=True)
    location_level_1 = models.IntegerField(db_index=True, null=True)
    location_level_2 = models.IntegerField(db_index=True, null=True)
    location_level_3 = models.IntegerField(db_index=True, null=True)
    location_level_4 = models.IntegerField(db_index=True, null=True)
    location_level_5 = models.IntegerField(db_index=True, null=True)
    location_level_6 = models.IntegerField(db_index=True, null=True)
    location_level_7 = models.IntegerField(db_index=True, null=True)

    is_archived = models.NullBooleanField()

    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)

    location_last_modified = models.DateTimeField()
    location_created_on = models.DateTimeField(null=True)

    @classmethod
    def dependencies(cls):
        return [LOCATION_STAGING_SLUG]


class DomainDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for Domain

    Grain: domain_id
    '''
    slug = DOMAIN_DIM_SLUG

    domain = models.CharField(max_length=255)
    domain_id = models.CharField(max_length=255, unique=True)
    default_timezone = models.CharField(max_length=255)
    hr_name = models.CharField(max_length=255, null=True)
    creating_user_id = models.CharField(max_length=255, null=True)
    project_type = models.CharField(max_length=255, null=True)

    is_active = models.BooleanField()
    case_sharing = models.BooleanField()
    commtrack_enabled = models.BooleanField()
    is_test = models.BooleanField()
    location_restriction_for_users = models.NullBooleanField()
    use_sql_backend = models.NullBooleanField()
    first_domain_for_user = models.NullBooleanField()

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
    # TODO: Write Update SQL Query
    slug = USER_LOCATION_DIM_SLUG

    domain = models.CharField(max_length=255)
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    location_dim = models.ForeignKey('LocationDim', on_delete=models.CASCADE)

    @classmethod
    def dependencies(cls):
        return [USER_DIM_SLUG, LOCATION_DIM_SLUG, USER_STAGING_SLUG]


class UserGroupDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for User and Group mapping

    Grain: user_id, group_id
    '''
    slug = USER_GROUP_DIM_SLUG

    domain = models.CharField(max_length=255)
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    group_dim = models.ForeignKey('GroupDim', on_delete=models.CASCADE)

    @classmethod
    def dependencies(cls):
        return [USER_DIM_SLUG, GROUP_DIM_SLUG, GROUP_STAGING_SLUG]


class ApplicationDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for Applications

    Grain: application_id
    '''
    slug = APPLICATION_DIM_SLUG

    domain = models.CharField(max_length=255)
    application_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    application_last_modified = models.DateTimeField(null=True)
    version = models.IntegerField(null=True)
    copy_of = models.CharField(max_length=255, null=True, blank=True)

    @classmethod
    def dependencies(cls):
        return [APPLICATION_STAGING_SLUG]


class DomainMembershipDim(BaseDim, CustomSQLETLMixin):
    '''
    Dimension for domain memberships for Web/CommCare users
    '''
    slug = DOMAIN_MEMBERSHIP_DIM_SLUG

    domain = models.CharField(max_length=255)
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    is_domain_admin = models.BooleanField()

    @classmethod
    def dependencies(cls):
        return [USER_STAGING_SLUG, USER_DIM_SLUG]

    class Meta:
        unique_together = ('domain', 'user_dim')
