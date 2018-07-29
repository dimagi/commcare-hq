from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date, timedelta
import json

from django.core.management import BaseCommand
from django.core.management.base import CommandError
from corehq.apps.analytics.signals import get_domain_membership_properties, get_subscription_properties_by_user
from corehq.apps.analytics.tasks import batch_track_on_hubspot, get_ab_test_properties
from corehq.apps.es.users import UserES
from corehq.apps.users.models import WebUser


class Command(BaseCommand):
    help = ("Updates given Hubspot properties for all users active within last 6 months. "
            "Only subscription, domain-membership, and A/B Test properties are supported")

    def add_arguments(self, parser):
        parser.add_argument(
            'property_names',
            metavar='property_name',
            nargs='+',
        )

    def handle(self, property_names, **options):
        print("Calculating properties for users")
        users = self.get_active_users()
        data_to_submit = [self.get_user_data(user, property_names)
                          for user in users if user.email and user.analytics_enabled]
        json_data = json.dumps(data_to_submit)

        print("Sending data to Hubspot")
        batch_track_on_hubspot(json_data)
        print("Update success.")

    @classmethod
    def get_active_users(cls):
        six_months_ago = date.today() - timedelta(days=180)
        users = UserES().web_users().last_logged_in(gte=six_months_ago).run().hits
        return [WebUser.wrap(u) for u in users]

    @classmethod
    def get_user_data(cls, couch_user, property_names):
        hubspot_properties = {}
        hubspot_properties.update(get_subscription_properties_by_user(couch_user))
        hubspot_properties.update(get_domain_membership_properties(couch_user))
        hubspot_properties.update(get_ab_test_properties(couch_user))

        try:
            data = [{"property": prop, "value": hubspot_properties[prop]} for prop in property_names]
        except KeyError:
            raise CommandError("Property should be one of following\n{}".format(
                list(hubspot_properties)
            ))
        user_data = {
            "email": couch_user.email,
            "properties": data
        }
        return user_data
