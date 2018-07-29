from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from dimagi.utils.post import post_file


class Command(BaseCommand):
    help = "Posts a single form to a url."

    def add_arguments(self, parser):
        parser.add_argument('file')
        parser.add_argument('url')

    def handle(self, file, url, **options):
        resp, errors = post_file(file, url)
        print("Got response:\n%s" % resp)
