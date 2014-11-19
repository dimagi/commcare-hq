from django.db import models


class Dhis2OrgUnit(models.Model):
    remote_id = models.IntegerField(
        help_text='Stored as a custom field on a mobile worker called dhis2_organization_unit_id',
        db_index=True, unique=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('Dhis2OrgUnit', null=True, blank=True)

    def delete(self, *args, **kwargs):
        # TODO: Make sure this organization unit is not in use
        # TODO: Try to delete children
        super(Dhis2OrgUnit, self).delete(*args, **kwargs)
