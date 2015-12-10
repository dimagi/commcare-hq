from django.contrib.auth.models import User
from django.core.management.base import LabelCommand
import sys
from corehq.apps.tour.models import GuidedTours


class Command(LabelCommand):
    help = "marks a tour with tour_slug as seen for all existing users"
    args = "tour_slug"

    def handle(self, tour_slug, *args, **kwargs):
        if len(args) > 0:
            username = args[0]
            confirm = raw_input("""MARK Tour {tour_slug} as SEEN for User {username}?
    Type 'yes' to continue or 'no' to cancel: """.format(tour_slug=tour_slug, username=username))
            if confirm == 'yes':
                user = User.objects.filter(username=username).first()
                GuidedTours.mark_as_seen(user, tour_slug)
                print("Complete")
        else:
            confirm = raw_input("""MARK Tour {tour_slug} as SEEN for ALL USERS?
    Type 'yes' to continue or 'no' to cancel: """.format(tour_slug=tour_slug))
            if confirm == 'yes':
                for user in User.objects.all():
                    sys.stdout.write(".")
                    GuidedTours.mark_as_seen(user, tour_slug)
                sys.stdout.write("\n")
                print("Complete")
