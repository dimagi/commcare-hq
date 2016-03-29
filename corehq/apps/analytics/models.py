import json

from django.db import models
from corehq.toggles import deterministic_random
from .tasks import update_hubspot_properties, batch_track_on_hubspot
from .utils import get_active_users

class ABType(object):
    HUBSPOT = "Hubspot"

    CHOICES = (
        (HUBSPOT, HUBSPOT)
    )

class AB(models.Model):
    partition = models.FloatField(default=0)
    slug = models.CharField(max_length=80)
    description = models.CharField(max_length=128)

    class Meta:
        abstract = True

    def assign_user(self, user):
        raise NotImplementedError


class HubspotAB(AB):
    def assign_user(self, user):
        update_hubspot_properties(user.username, self.get_test_group(user))

    def get_test_group(self, user):
        return {'ab_test_' + self.slug: 'A' if deterministic_random(user.username + self.slug) > self.partition else 'B'}

    @staticmethod
    def get_properties_for_user(user):
        return {
            'ab_test_' + test.slug: 'A' if deterministic_random(user.username + test.slug) > test.partition else 'B'
            for test in HubspotAB.objects.all()
        }

    def update_all_users(self):
        users = get_active_users()
        data = [{'email': user.username, 'properties': self.get_test_group(user)} for user in users]
        json_data = json.dumps(data)
        batch_track_on_hubspot(json_data)


from .signals import *
