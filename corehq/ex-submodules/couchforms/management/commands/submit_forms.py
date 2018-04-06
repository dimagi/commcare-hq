from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
import os
from dimagi.utils.post import post_file


class Command(BaseCommand):
    help = "Submits forms to a url."

    def add_arguments(self, parser):
        parser.add_argument('directory')
        parser.add_argument('post_url')

    def handle(self, directory, post_url, **options):
        for file in os.listdir(directory):
            print(post_file(os.path.join(directory, file), post_url))
