from django.core.management.base import LabelCommand, CommandError
import os
from dimagi.utils.post import post_file


class Command(LabelCommand):
    help = "Submits forms to a url."
    args = ""
    label = ""

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Usage: manage.py submit_forms <directory> <post url>')
        dir = args[0]
        url = args[1]
        for file in os.listdir(dir):
            print post_file(os.path.join(dir, file), url)
