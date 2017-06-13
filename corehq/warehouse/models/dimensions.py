from django.db import models


class BaseDim(models.Model):
    domain = models.CharField(max_length=255)

    dim_last_modified = models.DateTimeField(auto_now=True)
    dim_created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UserDim(BaseDim):
    user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.CharField(max_length=255)
    user_type = models.CharField(max_length=100)

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
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    location_dim = models.ForeignKey('LocationDim', on_delete=models.CASCADE)


class UserGroupDim(BaseDim):
    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    group_dim = models.ForeignKey('GroupDim', on_delete=models.CASCADE)
