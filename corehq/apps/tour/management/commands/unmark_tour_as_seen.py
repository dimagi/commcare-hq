from django.contrib.auth.models import User
from django.core.management.base import LabelCommand
import sys
from corehq.apps.tour.models import GuidedTour

CONFIRM_SINGLE_USER = """Unmark Tour {tour_slug} as seen for User {username}?
    Type 'yes' to continue or 'no' to cancel: """

CONFIRM_ALL_USERS = """Unmark Tour {tour_slug} for as seen ALL USERS?
    Type 'yes' to continue or 'no' to cancel: """


class Command(LabelCommand):
    help = "marks a tour with tour_slug as not seen for all existing users"
    args = "tour_slug <specific user>"

    def handle(self, tour_slug, *args, **kwargs):
        if len(args) > 0:
            username = args[0]
            confirm = raw_input(CONFIRM_SINGLE_USER.format(
                tour_slug=tour_slug, username=username))
            if confirm == 'yes':
                user = User.objects.filter(username=username).first()
                query = GuidedTour.objects.filter(tour_slug=tour_slug, user=user)
                print ("Found {} to delete".format(query.count()))
                query.all().delete()
                print("Complete")
        else:
            confirm = raw_input(CONFIRM_ALL_USERS.format(tour_slug=tour_slug))
            if confirm == 'yes':
                query = GuidedTour.objects.filter(tour_slug=tour_slug)
                print ("Found {} to delete".format(query.count()))
                query.all().delete()
                print("Complete")
