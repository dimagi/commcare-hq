from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from ...models import Toggle


class Command(BaseCommand):
    help = "Makes a toggle."

    def add_arguments(self, parser):
        parser.add_argument(
            'slug',
        )
        parser.add_argument(
            'usernames',
            metavar='username',
            nargs='*',
        )
     
    def handle(self, slug, usernames, **options):
        toggle = Toggle(slug=slug, enabled_users=usernames)
        toggle.save()

