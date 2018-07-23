from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from six.moves import input

CONFIRM_SINGLE_USER = """Unmark Tour {tour_slug} as seen for User {username}?
    Type 'yes' to continue or 'no' to cancel: """

CONFIRM_ALL_USERS = """Unmark Tour {tour_slug} for as seen ALL USERS?
    Type 'yes' to continue or 'no' to cancel: """


class Command(BaseCommand):
    help = "marks a tour with tour_slug as not seen for all existing users"

    def add_arguments(self, parser):
        parser.add_argument('tour_slug')
        parser.add_argument('user', nargs='?')

    def handle(self, tour_slug, **options):
        if options['user']:
            username = options['user']
            confirm = input(CONFIRM_SINGLE_USER.format(
                tour_slug=tour_slug, username=username))
            if confirm == 'yes':
                user = User.objects.filter(username=username).first()
                print("Complete")
        else:
            confirm = input(CONFIRM_ALL_USERS.format(tour_slug=tour_slug))
            if confirm == 'yes':
                print("Complete")
