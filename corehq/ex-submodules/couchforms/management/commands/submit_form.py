from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import CommandError, BaseCommand
import os
from dimagi.utils.post import post_data


class Command(BaseCommand):
    help = "Submits a single form to a url with options."

    def add_arguments(self, parser):
        parser.add_argument(
            'filename',
        )
        parser.add_argument(
            'url',
        )
        parser.add_argument(
            'file',
            dest='files',
            nargs='*',
        )
        parser.add_argument(
            '--method',
            action='store',
            choices=['curl', 'python'],
            dest='method',
            default='curl',
            help='Method to upload (curl, python), defaults to curl',
            type=str,
        )
        parser.add_argument(
            '--chunked',
            action='store_true',
            dest='use_chunked',
            default=False,
            help='Use chunked encoding (default=False)',
        )
        parser.add_argument(
            '--odk',
            action='store_true',
            dest='is_odk',
            default=False,
            help='Simulate ODK submission (default=False)',
        )

    def handle(self, filename, url, files, **options):
        use_curl = options['method'] == 'curl'
        use_chunked = options['use_chunked']
        is_odk = options['is_odk']

        attachments = []
        for attach_path in files:
            if not os.path.exists(attach_path):
                raise CommandError("Error, additional file path does not exist: %s" % attach_path)
            else:
                attachments.append((attach_path.replace('.', '_'), attach_path))

        print(post_data(None, url, path=file, use_curl=use_curl, use_chunked=use_chunked,
                        is_odk=is_odk, attachments=attachments))
