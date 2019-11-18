import io
import zipfile

from django.core.management.base import BaseCommand

from corehq.blobs import get_blob_db

USAGE = "Usage: ./manage.py import_blob_zip <zipname>"


class Command(BaseCommand):
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('zipname')

    def handle(self, zipname, **options):
        from_zip = zipfile.ZipFile(zipname)
        to_db = get_blob_db()
        for key in from_zip.namelist():
            blob = io.BytesIO(from_zip.read(key))
            to_db.copy_blob(blob, key=key)
