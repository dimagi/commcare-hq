from __future__ import print_function
from django.core.management.base import BaseCommand, CommandError
from dimagi.utils.post import post_file


class Command(BaseCommand):
    help = "Posts a single form to a url."
    args = ""
    label = ""

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Usage: manage.py post_from <file> <post url>')
        file = args[0]
        url = args[1]
        resp, errors = post_file(file, url)
        print("Got response:\n%s" % resp)
