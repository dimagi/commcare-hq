from __future__ import print_function
from __future__ import absolute_import
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
import sys
from corehq.apps.tour.models import GuidedTour
from six.moves import input

CONFIRM_FOR_SINGLE_USER = """MARK Tour {tour_slug} as SEEN for User {username}?
    Type 'yes' to continue or 'no' to cancel: """

CONFIRM_FORM_ALL_USERS = """MARK Tour {tour_slug} as SEEN for ALL USERS?
    Type 'yes' to continue or 'no' to cancel: """


class Command(BaseCommand):
    help = "marks a tour with tour_slug as seen for all existing users"

    def add_arguments(self, parser):
        parser.add_argument('tour_slug')

    def handle(self, tour_slug, *args, **kwargs):
        if len(args) > 0:
            username = args[0]
            confirm = input(CONFIRM_FOR_SINGLE_USER.format(
                tour_slug=tour_slug, username=username))
            if confirm == 'yes':
                user = User.objects.filter(username=username).first()
                GuidedTour.mark_as_seen(user, tour_slug)
                print("Complete")
        else:
            confirm = input(CONFIRM_FORM_ALL_USERS.format(tour_slug=tour_slug))
            if confirm == 'yes':
                for user in User.objects.all():
                    sys.stdout.write(".")
                    GuidedTour.mark_as_seen(user, tour_slug)
                sys.stdout.write("\n")
                print("Complete")
