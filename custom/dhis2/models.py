from django.db import models


# TODO: Do we want all this? We don't care. We want the ID and the name, and maybe the parent/children


class Dhis2OrgUnitAccess(models.Model):
    update = models.BooleanField()
    externalize = models.BooleanField()
    delete = models.BooleanField()
    write = models.BooleanField()
    read = models.BooleanField()
    manage = models.BooleanField()


class Dhis2OrgUnit(models.Model):
    # List/summary attributes
    dhis2_id = models.CharField(
        max_length=64,  # Only ever seen 11-char IDs, but who knows, right?
        help_text='Stored as a custom field on a mobile worker called dhis2_organization_unit_id',
        db_index=True, unique=True)
    name = models.CharField(max_length=255)
    created = models.DateTimeField()
    last_updated = models.DateTimeField(null=True, blank=True)
    code = models.CharField(max_length=128, blank=True)  # Code is user-defined
    href = models.CharField(max_length=255, blank=True)
    # Detail attributes
    # level = models.IntegerField()
    # uuid = models.CharField(max_length=36)
    # short_name = models.CharField()
    # feature_type = models.CharField()
    # external_access = models.BooleanField()
    # coordinates = models.CharField()
    # active = models.BooleanField()
    # display_name = models.CharField()
    parent = models.ForeignKey('Dhis2OrgUnit', null=True, blank=True, related_name='children')
    access = models.OneToOneField(Dhis2OrgUnitAccess)
    # users
    # organisation_unit_groups
    # children  # See parent related_name
    # data_sets
    # attribute_values
    # user_group_accesses

    def delete(self, *args, **kwargs):
        # TODO: Make sure this organization unit is not in use
        # TODO: Try to delete children
        super(Dhis2OrgUnit, self).delete(*args, **kwargs)
