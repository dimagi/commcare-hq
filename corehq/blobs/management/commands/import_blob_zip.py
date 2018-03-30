from __future__ import absolute_import
from __future__ import unicode_literals
import io
import zipfile

from django.core.management.base import BaseCommand

from corehq.blobs import BlobInfo, get_blob_db

USAGE = "Usage: ./manage.py import_blob_zip <zipname>"


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('zipname')

    def handle(self, zipname, **options):
        from_zip = zipfile.ZipFile(zipname)

        to_db = get_blob_db()

        for filename in from_zip.namelist():
            bucket = '/'.join(filename.split('/')[:-1])
            identifier = filename.split('/')[-1]
            blob = io.BytesIO(from_zip.read(filename))
            # copy_blob only needs the identifier
            blob_info = BlobInfo(identifier=identifier, length="", digest="")
            to_db.copy_blob(blob, blob_info, bucket)
