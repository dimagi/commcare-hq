from __future__ import absolute_import

import os

from django.core.management.base import BaseCommand

from corehq.apps.dropbox.utils import upload_to_dropbox


class Command(BaseCommand):
    help = "Upload a file from disk to dropbox"

    def add_arguments(self, parser):
        parser.add_argument('file_path')
        parser.add_argument('token', help='Dropbox access token.')
        parser.add_argument('--dropbox-path', help='Path to store file to in Dropbox.')

    def handle(self, file_path, token, **options):
        dropbox_path = options.get('dropbox_path') or '/{}'.format(os.path.basename(file_path))
        size = os.path.getsize(file_path)

        def progress_callback(bytes_uploaded, size=size):
            print('Progress: %s' % int(100 * float(bytes_uploaded) / size))

        upload_to_dropbox(token, dropbox_path, file_path, progress_callback)
