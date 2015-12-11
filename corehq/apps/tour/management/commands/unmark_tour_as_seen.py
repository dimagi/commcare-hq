from django.contrib.auth.models import User
from django.core.management.base import LabelCommand
import sys
from corehq.apps.tour.models import GuidedTours

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
                tours, _ = GuidedTours.objects.get_or_create(user=user)
                if tour_slug in tours.seen_tours:
                    del tours.seen_tours[tour_slug]
                    tours.save()
                print("Complete")
        else:
            confirm = raw_input(CONFIRM_ALL_USERS.format(tour_slug=tour_slug))
            if confirm == 'yes':
                for tours in GuidedTours.objects.all():
                    if tour_slug in tours.seen_tours:
                        sys.stdout.write('.')
                        del tours.seen_tours[tour_slug]
                        tours.save()
                sys.stdout.write("\n")
                print("Complete")
