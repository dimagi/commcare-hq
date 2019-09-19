from django.db import models


class BaseDim(models.Model):
    batch = models.ForeignKey(
        'Batch',
        on_delete=models.PROTECT,
    )

    dim_last_modified = models.DateTimeField(auto_now=True)
    dim_created_on = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField()

    class Meta:
        abstract = True


class UserDim(BaseDim):
    """
    Dimension for Users

    Grain: user_id
    """
    user_id = models.CharField(max_length=255, unique=True)
    username = models.CharField(max_length=150)
    user_type = models.CharField(max_length=100)
    first_name = models.TextField(null=True)
    last_name = models.TextField(null=True)
    email = models.CharField(max_length=255, null=True)
    doc_type = models.CharField(max_length=100)

    is_active = models.NullBooleanField()
    is_staff = models.NullBooleanField()
    is_superuser = models.NullBooleanField()

    last_login = models.DateTimeField(null=True)
    date_joined = models.DateTimeField()


class GroupDim(BaseDim):
    """
    Dimension for Groups

    Grain: group_id
    """
    group_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    case_sharing = models.NullBooleanField()
    reporting = models.NullBooleanField()

    group_last_modified = models.DateTimeField()


class LocationDim(BaseDim):
    """
    Dimension for Locations

    Grain: location_id
    """
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


class DomainDim(BaseDim):
    """
    Dimension for Domain

    Grain: domain_id
    """
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


class UserLocationDim(BaseDim):
    """
    Dimension for User and Location mapping

    Grain: user_id, location_id
    """
    domain = models.CharField(max_length=255)
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    location_dim = models.ForeignKey('LocationDim', on_delete=models.CASCADE)


class UserGroupDim(BaseDim):
    """
    Dimension for User and Group mapping

    Grain: user_id, group_id
    """
    domain = models.CharField(max_length=255)
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    group_dim = models.ForeignKey('GroupDim', on_delete=models.CASCADE)


class ApplicationDim(BaseDim):
    """
    Dimension for Applications

    Grain: application_id
    """
    domain = models.CharField(max_length=255)
    application_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    application_last_modified = models.DateTimeField(null=True)
    version = models.IntegerField(null=True)
    copy_of = models.CharField(max_length=255, null=True, blank=True)


class DomainMembershipDim(BaseDim):
    """
    Dimension for domain memberships for Web/CommCare users
    """
    domain = models.CharField(max_length=255)
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    is_domain_admin = models.BooleanField()

    class Meta:
        unique_together = ('domain', 'user_dim')
