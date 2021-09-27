from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, get_location
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.users.models import WebUser
from django.db import models


class FacilityInCharge(models.Model):
    user_id = models.CharField(max_length=128, db_index=True)
    location = models.ForeignKey(SQLLocation, on_delete=models.PROTECT)

    class Meta(object):
        app_label = 'ewsghana'


class EWSExtension(models.Model):
    user_id = models.CharField(max_length=128, db_index=True)
    domain = models.CharField(max_length=128)
    location_id = models.CharField(max_length=128, null=True, db_index=True)
    sms_notifications = models.BooleanField(default=False)

    @property
    def supply_point(self):
        if not self.location_id:
            return
        return get_location(self.location_id).linked_supply_point()

    @property
    def web_user(self):
        return WebUser.get(self.user_id)

    @property
    def verified_number(self):
        return PhoneNumber.get_two_way_number(self.phone_number)

    @property
    def domain_object(self):
        return Domain.get_by_name(self.domain)

    class Meta(object):
        app_label = 'ewsghana'


class SQLNotification(models.Model):
    domain = models.CharField(max_length=128)
    user_id = models.CharField(max_length=128)
    type = models.CharField(max_length=128)
    week = models.IntegerField()
    year = models.IntegerField()

    class Meta(object):
        app_label = 'ewsghana'
